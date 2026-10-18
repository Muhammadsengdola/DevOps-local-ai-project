import os
import re
import html
import sys
from datetime import datetime

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from crewai import Agent, Crew, LLM, Process, Task
import requests
from pypdf import PdfReader

# ==========================================
# ค่าตั้งต้น (ปรับได้ผ่าน environment variable)
# ==========================================
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))          # context ที่ส่งให้ Ollama (ค่าเริ่มต้นของ Ollama เล็กมาก ข้อความยาวจะโดนตัดทิ้งเงียบๆ)
CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "6000"))  # ขนาดข้อความต่อการอ่าน 1 รอบ (ภาษาไทยกิน token เยอะ อย่าตั้งใหญ่เกิน)
MAX_CHAT_TURNS = 6                                   # Mode A จำบทสนทนาย้อนหลังกี่รอบ
VERBOSE = os.getenv("CREW_VERBOSE", "1") == "1"
os.environ.setdefault("OPENAI_API_KEY", "ollama")    # กัน CrewAI บางเวอร์ชันบ่นหา key

MODELS = {
    "1": ("qwen2.5:14b-instruct", "Qwen 2.5 (14B Instruct)"),
    "2": ("qwen2.5:7b-instruct", "Qwen 2.5 (7B Instruct)"),
}
CODE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs",
             ".php", ".rb", ".kt", ".swift", ".sql", ".sh", ".html", ".css", ".vue", ".dart", ".lua"}
CODE_EXT_BY_LANG = {
    "python": "py", "py": "py", "javascript": "js", "js": "js", "typescript": "ts", "ts": "ts",
    "jsx": "jsx", "tsx": "tsx", "html": "html", "css": "css", "java": "java", "c": "c",
    "cpp": "cpp", "c++": "cpp", "csharp": "cs", "c#": "cs", "cs": "cs", "go": "go", "rust": "rs",
    "php": "php", "ruby": "rb", "kotlin": "kt", "swift": "swift", "sql": "sql", "bash": "sh",
    "sh": "sh", "shell": "sh", "yaml": "yml", "yml": "yml", "json": "json", "dart": "dart", "lua": "lua",
}
# ตัวอักษรจีน + เครื่องหมายวรรคตอนจีน/ตัวเต็มความกว้าง (，。：) ที่ Qwen ชอบหลุดออกมา
CJK = re.compile(r"[　-〿㐀-鿿＀-￯]")


# ==========================================
# ตั้งค่าก่อนรัน
# ==========================================
def choose(title, options, default):
    print(title)
    for key, label in options.items():
        print(f"  [{key}] {label}")
    picked = input(f"👉 เลือกหมายเลข (Enter = {default}): ").strip()
    return picked if picked in options else default


def get_runtime_settings(export_kind="report", ask_export=True):
    print("\n--- ⚙️ ตั้งค่าตัวเลือกการทำงาน (Runtime Settings) ---")
    m = choose("1. เลือกโมเดล AI:", {
        "1": "qwen2.5:14b-instruct (แม่นกว่า คิดซับซ้อนได้ดีกว่า แต่ช้ากว่า)",
        "2": "qwen2.5:7b-instruct  (เร็ว ใช้ทรัพยากรน้อย)",
    }, "2")
    lang = choose("\n2. เลือกภาษาผลลัพธ์:", {"1": "ภาษาไทย", "2": "English"}, "1")

    export = "1"
    if ask_export:
        if export_kind == "code":
            opts = {"1": "แสดงบน Terminal อย่างเดียว",
                    "2": "บันทึก .md (โค้ด + คำอธิบาย)",
                    "3": "บันทึกเป็นไฟล์โค้ด (เลือกนามสกุลตามภาษาให้อัตโนมัติ)"}
        else:
            opts = {"1": "แสดงบน Terminal อย่างเดียว", "2": "บันทึก .txt",
                    "3": "บันทึก .md (Markdown)", "4": "บันทึก .html (เปิดในเบราว์เซอร์ได้)"}
        export = choose("\n3. เลือกรูปแบบการบันทึกไฟล์:", opts, "1")

    detail = choose("\n4. เลือกระดับความลึกของเนื้อหา:",
                    {"1": "กระชับ (Short & Concise)", "2": "ละเอียดเชิงลึก (Detailed)"}, "1")

    model, model_name = MODELS[m]
    s = {
        "model": model, "model_name": model_name,
        "language": "Thai" if lang == "1" else "English",
        "export": export, "export_kind": export_kind,
        "detail": "short" if detail == "1" else "detailed",
    }
    print(f"\n✅ ตั้งค่าสำเร็จ! [โมเดล: {model_name} | ภาษา: {s['language']} | ระดับ: {s['detail']}]\n")
    return s


# ==========================================
# กฎ prompt (เขียนเป็นอังกฤษ เพราะโมเดลเล็กทำตามคำสั่งภาษาอังกฤษได้แม่นกว่า แต่ให้ตอบเป็นภาษาที่เลือก)
# ==========================================
def lang_rule(s):
    if s["language"] == "Thai":
        return ("Write the whole answer in Thai (ภาษาไทย). Keep code, commands, file names and "
                "technical terms in English. Never use Chinese characters.")
    return "Write the whole answer in English. Never use Chinese characters."


def detail_rule(s):
    if s["detail"] == "short":
        return "Be concise: get straight to the point, about 150-200 words or 5-7 bullet points at most."
    return "Be thorough: explain the reasoning, give concrete examples, and organize the answer with headings."


def heading(s, thai, english):
    return thai if s["language"] == "Thai" else english


# ==========================================
# LLM / Agent helpers
# ==========================================
def ensure_ctx_model(base):
    """CrewAI รุ่นใหม่คุยกับ Ollama ผ่าน OpenAI-compatible API ซึ่งส่ง num_ctx ตรงๆ ไม่ได้
    จึงสร้างโมเดลสำเนาที่ฝัง num_ctx ไว้ (สร้างครั้งเดียว ไม่ซ้ำน้ำหนักโมเดล) แล้วใช้ชื่อนั้นแทน"""
    name = f"{base}-ctx{NUM_CTX}"
    try:
        have = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10).json().get("models", [])
        if any(m.get("name") == name for m in have):
            return name
        print(f"🔧 สร้างโมเดล {name} (context {NUM_CTX}) ครั้งแรกเท่านั้น ...")
        r = requests.post(f"{OLLAMA_URL}/api/create", timeout=300,
                          json={"model": name, "from": base, "parameters": {"num_ctx": NUM_CTX},
                                "stream": False})
        r.raise_for_status()
        return name
    except Exception as ex:
        print(f"⚠️ ตั้ง context {NUM_CTX} ไม่สำเร็จ ({ex}) → ใช้ {base} ตามค่าเริ่มต้นของ Ollama")
        return base


def make_llm(s, temperature=0.3):
    if "ctx_model" not in s:
        s["ctx_model"] = ensure_ctx_model(s["model"])
    return LLM(model=f"ollama/{s['ctx_model']}", base_url=OLLAMA_URL, temperature=temperature)


def ask_llm(llm, messages, s=None):
    """เรียกโมเดลตรงๆ (ไม่ผ่าน CrewAI) และถ้าหลุดภาษาจีนจะสั่งเขียนใหม่ 1 รอบ"""
    reply = str(llm.call(messages)).strip()
    if s and len(CJK.findall(reply)) > 5:
        retry = messages + [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": f"Your answer contains Chinese. Rewrite the same answer "
                                        f"fully in {s['language']} with no Chinese characters."},
        ]
        reply = str(llm.call(retry)).strip()
    return reply


def make_agent(role, goal, backstory, llm):
    return Agent(role=role, goal=goal, backstory=backstory, llm=llm,
                 verbose=VERBOSE, allow_delegation=False, max_iter=5)


def run_crew(agents, tasks):
    crew = Crew(agents=agents, tasks=tasks, process=Process.sequential, verbose=VERBOSE)
    return str(crew.kickoff())


# ==========================================
# จัดการข้อความ / ไฟล์
# ==========================================
def read_multiline(prompt):
    """input() ปกติอ่านได้บรรทัดเดียว วางข้อความยาวหลายบรรทัดจะหลุด จึงอ่านจนเจอ END"""
    print(prompt)
    print("   (วางได้หลายบรรทัด แล้วพิมพ์ END ในบรรทัดใหม่เพื่อจบ)")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def read_document(path):
    if path.lower().endswith(".pdf"):
        reader = PdfReader(path)
        pages = []
        for i, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"[Page {i}]\n{text}")
        return "\n\n".join(pages)

    with open(path, "rb") as f:
        raw = f.read()
    if b"\x00" in raw[:4096]:
        raise ValueError("ไฟล์นี้เป็นไฟล์ไบนารี ไม่ใช่ไฟล์ข้อความ/โค้ด")
    for enc in ("utf-8-sig", "cp874"):  # cp874 = ไฟล์ภาษาไทยจาก Windows รุ่นเก่า
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("อ่าน encoding ของไฟล์นี้ไม่ได้")


def chunk_text(text, size=CHUNK_CHARS):
    chunks, cur = [], ""
    for para in text.split("\n"):
        while len(para) > size:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(para[:size])
            para = para[size:]
        if len(cur) + len(para) + 1 > size:
            chunks.append(cur)
            cur = para
        else:
            cur = f"{cur}\n{para}" if cur else para
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c.strip()]


def condense(text, llm, s, kind="document", depth=0):
    """ข้อความยาวเกิน context → อ่านทีละส่วน จดโน้ต แล้วค่อยให้ agent ทำงานกับโน้ต (map-reduce)"""
    if len(text) <= CHUNK_CHARS or depth >= 2:
        return text
    chunks = chunk_text(text)
    print(f"📚 เนื้อหายาว {len(text):,} ตัวอักษร → แบ่งอ่านทีละส่วน {len(chunks)} ส่วน")
    if kind == "code":
        instr = ("You are reading ONE part of a source code file. In bullet points, explain: the functions/"
                 "classes defined and what each does (use their exact names), inputs/outputs, key logic, "
                 "and libraries or files used. Max 12 bullets. Do not guess about code you cannot see.")
    else:
        instr = ("You are reading ONE part of a long document. Write factual notes in bullet points: "
                 "main points, key arguments, important names/numbers/dates/definitions, and conclusions. "
                 "Max 12 bullets. Only use information that appears in the text.")
    notes = []
    for i, chunk in enumerate(chunks, 1):
        print(f"   🧩 กำลังอ่านส่วนที่ {i}/{len(chunks)} ...")
        out = ask_llm(llm, [
            {"role": "system", "content": f"{instr} {lang_rule(s)}"},
            {"role": "user", "content": f"Part {i} of {len(chunks)}:\n\n{chunk}"},
        ], s)
        notes.append(f"[Part {i}/{len(chunks)}]\n{out}")
    return condense("\n\n".join(notes), llm, s, kind, depth + 1)


# ==========================================
# บันทึกผลลัพธ์
# ==========================================
def extract_code_blocks(text):
    return re.findall(r"```([\w+#.-]*)[ \t]*\n([\s\S]*?)```", text)


def markdown_to_html(md_text, title):
    try:
        import markdown  # pip install markdown (ถ้าไม่มีจะแสดงเป็นข้อความธรรมดา)
        body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    except ImportError:
        body = f"<pre>{html.escape(md_text)}</pre>"
    return f"""<!DOCTYPE html>
<html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body{{font-family:"Sarabun","Noto Sans Thai",system-ui,sans-serif;max-width:860px;margin:40px auto;padding:0 16px;line-height:1.7;color:#222;background:#fff}}
pre{{background:#f4f4f4;padding:12px;overflow-x:auto;white-space:pre-wrap;border-radius:6px}}
table{{border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:6px 10px}}
</style></head><body>{body}</body></html>"""


def write_file(filename, content):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n📁 บันทึกไฟล์: {os.path.abspath(filename)}")


def save_output(base, content, s):
    content = str(content).strip()
    print("\n" + "=" * 42 + "\n📋 ผลลัพธ์สุดท้าย\n" + "=" * 42 + f"\n{content}\n")
    if s["export"] == "1":
        print("💻 แสดงผลบน Terminal เรียบร้อย (ไม่ได้บันทึกไฟล์)")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # กันไฟล์เก่าโดนทับ
    if s["export_kind"] == "code":
        blocks = extract_code_blocks(content)
        if s["export"] == "3" and blocks:
            lang, code = max(blocks, key=lambda b: len(b[1]))  # เอาบล็อกโค้ดที่ยาวสุด = โค้ดหลัก
            ext = CODE_EXT_BY_LANG.get(lang.lower(), "txt")
            write_file(f"{base}_{stamp}.{ext}", code.strip() + "\n")
            return
        if s["export"] == "3":
            print("⚠️ ไม่พบบล็อกโค้ดในผลลัพธ์ จึงบันทึกเป็น .md แทน")
        write_file(f"{base}_{stamp}.md", content)
        return

    if s["export"] == "2":
        write_file(f"{base}_{stamp}.txt", content)
    elif s["export"] == "3":
        write_file(f"{base}_{stamp}.md", content)
    elif s["export"] == "4":
        write_file(f"{base}_{stamp}.html", markdown_to_html(content, base))


# ==========================================
# Mode A: แชทอิสระ (เรียก LLM ตรง + จำบทสนทนา)
# ==========================================
def run_mode_a():
    print("\n==========================================")
    print("      Mode A: แชทสนทนากับ AI อิสระ          ")
    print("==========================================")
    s = get_runtime_settings(ask_export=False)
    llm = make_llm(s, temperature=0.5)
    system = ("You are a helpful and accurate assistant. Answer the user's latest message directly, "
              "using the earlier conversation as context. If you are not sure about a fact, say so "
              f"instead of guessing. {detail_rule(s)} {lang_rule(s)}")
    history = []
    print("💡 พิมพ์ 'exit' เพื่อกลับเมนูหลัก | '/clear' เพื่อล้างความจำบทสนทนา\n")

    while True:
        msg = input("\n👤 คุณ: ").strip()
        if msg.lower() == "exit":
            print("🔙 กำลังกลับสู่เมนูหลัก...")
            break
        if msg == "/clear":
            history.clear()
            print("🧹 ล้างความจำบทสนทนาแล้ว")
            continue
        if not msg:
            continue

        history.append({"role": "user", "content": msg})
        print("🤖 AI กำลังคิด...")
        try:
            recent = history[-(MAX_CHAT_TURNS * 2 + 1):]
            reply = ask_llm(llm, [{"role": "system", "content": system}] + recent, s)
        except Exception as ex:
            history.pop()
            print(f"❌ เรียกโมเดลไม่สำเร็จ: {ex}")
            continue
        history.append({"role": "assistant", "content": reply})
        print(f"\n🤖 AI:\n{reply}")


# ==========================================
# Mode B: เขียนโค้ด (Planner → Coder → Reviewer → Fixer)
# ==========================================
def run_mode_b():
    print("\n==========================================")
    print("  Mode B: ผู้ช่วยเขียนโค้ด & DevOps (4 Sub-Agents)")
    print("==========================================")
    prompt = read_multiline("💻 อธิบายโจทย์ให้ชัด (ภาษาที่ใช้, input/output, ตัวอย่าง ยิ่งละเอียดยิ่งดี):")
    if not prompt:
        return

    s = get_runtime_settings(export_kind="code")
    llm = make_llm(s, temperature=0.2)  # งานโค้ดใช้ temperature ต่ำ ลดการมั่ว
    rule = lang_rule(s)
    request = f"<request>\n{prompt}\n</request>"

    planner = make_agent(
        "Software Planner",
        "Turn the user's request into a short, concrete implementation plan a programmer can follow.",
        "You are a pragmatic software architect. You choose the simplest design that fully solves the "
        "request and use only standard libraries unless the request needs more.", llm)
    coder = make_agent(
        "Programmer",
        "Write complete, correct, runnable code that follows the plan exactly.",
        "You are a careful senior developer. You never leave placeholders, TODOs or '...' in code.", llm)
    reviewer = make_agent(
        "Code Reviewer",
        "Find real bugs that would crash the code or produce wrong results.",
        "You are a strict reviewer. You only report problems you can point to in the code, "
        "never style opinions or imagined issues.", llm)
    fixer = make_agent(
        "Code Fixer",
        "Apply the reviewer's fixes and deliver the final, complete code.",
        "You make minimal, precise edits and always return the full program, never a partial snippet.", llm)

    t_plan = Task(
        description=f"""User request:
{request}

Write an implementation plan. Do NOT write any code yet.
Rules:
- If the user did not name a programming language, use Python.
- Plan only what the request needs; no extra features.
- {detail_rule(s)}
- {rule}""",
        expected_output="""A plan with exactly these sections:
1. Goal (1-2 sentences)
2. Language and libraries
3. Inputs and outputs
4. Functions/classes to write (name + one-line purpose each)
5. Step-by-step logic
6. Edge cases to handle""",
        agent=planner)

    t_code = Task(
        description=f"""Original user request:
{request}

Write the code by following the plan from the previous task.
Rules:
- Put the whole program in ONE fenced code block with a language tag, e.g. ```python
- It must run as-is: all imports, all functions, and an entry point (e.g. main).
- No placeholders, no TODO, no '...'.
- After the code block, write 2-4 lines on how to run it. {rule}""",
        expected_output="One complete fenced code block, followed by brief run instructions.",
        agent=coder, context=[t_plan])

    t_review = Task(
        description=f"""Original user request:
{request}

Review the draft code from the previous task line by line. Check for:
syntax errors, missing imports, undefined names, logic that does not match the request,
edge cases from the plan that are not handled, and crashes on bad input.
Rules:
- Report at most 5 issues, most serious first.
- Only report issues you can quote from the code. No style or naming suggestions.
- If the code is correct, reply with exactly: NO_ISSUES
- {rule}""",
        expected_output="Either NO_ISSUES, or a numbered list where each item has: "
                        "Location (quote the code), Problem, Fix.",
        agent=reviewer, context=[t_plan, t_code])

    t_fix = Task(
        description=f"""You get the draft code and the review report.
Rules:
- If the review says NO_ISSUES, output the draft code unchanged.
- Otherwise fix ONLY the listed issues and keep everything else the same.
- Output the FULL final program in ONE fenced code block with a language tag (never a diff or partial code).
- After the code, add a short "Changes" list (or "No changes"), then how to run it. {rule}""",
        expected_output="The full final code in one fenced code block, then a short list of changes "
                        "and run instructions.",
        agent=fixer, context=[t_code, t_review])  # ต้องเห็นทั้งโค้ดและรายงานบัค

    result = run_crew([planner, coder, reviewer, fixer], [t_plan, t_code, t_review, t_fix])
    save_output("code_result", result, s)


# ==========================================
# Mode C: วิเคราะห์ PDF (Summarizer → Titles, Reviewer → Grader)
# ==========================================
def run_mode_c():
    print("\n==========================================")
    print("  Mode C: วิเคราะห์ PDF ด้วย Sub-Agent 4 ตัว  ")
    print("==========================================")
    path = input("📁 พิมพ์ชื่อหรือพาธไฟล์ PDF (เช่น article.pdf): ").strip().strip('"')
    if not os.path.isfile(path) or not path.lower().endswith(".pdf"):
        print(f"❌ ไม่พบไฟล์ PDF '{path}'")
        return

    print(f"📄 กำลังอ่านข้อความจากไฟล์ {path}...")
    content = read_document(path)
    if not content.strip():
        print("❌ ไม่พบข้อความใน PDF (อาจเป็นไฟล์ภาพสแกน ต้องทำ OCR ก่อน)")
        return

    s = get_runtime_settings()
    llm = make_llm(s, temperature=0.3)
    notes = condense(content, llm, s)
    doc = f"<document>\n{notes}\n</document>"
    rule = lang_rule(s)

    summarizer = make_agent("Summarizer", "Summarize documents accurately without adding outside information.",
                            "You are an expert at condensing long documents into clear key points.", llm)
    titler = make_agent("Title Specialist", "Write accurate, catchy titles that reflect the real content.",
                        "You are an experienced editor who writes headlines.", llm)
    critic = make_agent("Critical Reviewer", "Evaluate strengths and weaknesses fairly, with evidence.",
                        "You are a professional reviewer who backs every point with something from the text.", llm)
    grader = make_agent("Grader", "Score the document from 1-10 using a clear rubric.",
                        "You are a teacher who grades writing consistently and explains each score.", llm)

    t_sum = Task(
        description=f"""{doc}

Summarize the document above.
- Start with ONE sentence saying what the document is about.
- Then list the key points as bullet points.
- Only use information from the document.
- {detail_rule(s)}
- {rule}""",
        expected_output="A one-sentence overview, then key points as bullet points.",
        agent=summarizer)

    t_title = Task(
        description=f"""Using the summary from the previous task, propose exactly 3 titles for the document:
1) formal/academic  2) news headline  3) catchy/creative.
Each title is at most 15 words and is followed by one line explaining why it fits.
{rule}""",
        expected_output="A numbered list of exactly 3 titles, each with a one-line reason.",
        agent=titler, context=[t_sum])

    t_review = Task(
        description=f"""{doc}

Analyze the strengths and weaknesses of the document above (content, evidence, structure, clarity).
- Give 3-5 strengths and 3-5 weaknesses; each must refer to something specific in the document.
- End with 2-3 concrete suggestions for improvement.
- {detail_rule(s)}
- {rule}""",
        expected_output="Three sections — Strengths, Weaknesses, Suggestions — each as bullet points.",
        agent=critic)

    t_grade = Task(
        description=f"""Using the summary and the review from previous tasks, grade the document.
Score each criterion from 1-10 with a one-line reason:
1. Content accuracy and depth
2. Structure and organization
3. Clarity of writing
4. Usefulness to the reader
Then give the overall score (average, 1 decimal place) and 2-3 sentences justifying it.
{rule}""",
        expected_output="4 criterion scores with reasons, then the overall score and justification.",
        agent=grader, context=[t_sum, t_review])

    run_crew([summarizer, titler, critic, grader], [t_sum, t_title, t_review, t_grade])

    # เดิมใช้ผลของ crew ตรงๆ ซึ่งได้แค่ผลของ task สุดท้าย (คะแนน) → รวมทุกส่วนเอง
    report = "\n\n".join([
        f"# {heading(s, 'ผลวิเคราะห์เอกสาร', 'Document Analysis')}: {os.path.basename(path)}",
        f"## {heading(s, 'ชื่อบทความที่แนะนำ', 'Suggested Titles')}\n\n{t_title.output.raw}",
        f"## {heading(s, 'สรุปสาระสำคัญ', 'Summary')}\n\n{t_sum.output.raw}",
        f"## {heading(s, 'ข้อดีและข้อเสีย', 'Strengths & Weaknesses')}\n\n{t_review.output.raw}",
        f"## {heading(s, 'คะแนนประเมิน', 'Score')}\n\n{t_grade.output.raw}",
    ])
    save_output("pdf_analysis", report, s)


# ==========================================
# Mode D: สรุปข้อความยาวแบบด่วน (Extractor → Formatter)
# ==========================================
def run_mode_d():
    print("\n==========================================")
    print("  Mode D: สรุปข้อความยาวแบบด่วน (2 Sub-Agents) ")
    print("==========================================")
    text = read_multiline("📝 วางข้อความที่ต้องการให้สรุป:")
    if not text:
        return

    s = get_runtime_settings()
    llm = make_llm(s, temperature=0.3)
    text = condense(text, llm, s)
    rule = lang_rule(s)
    max_points = 5 if s["detail"] == "short" else 10

    extractor = make_agent("Core Extractor", "Pull out the most important points of a text without distorting them.",
                           "You are an analyst who separates key information from filler.", llm)
    formatter = make_agent("Format Specialist", "Turn raw points into a clean, easy-to-read summary.",
                           "You are an editor who makes information quick to scan.", llm)

    t_extract = Task(
        description=f"""<text>
{text}
</text>

Extract the main points of the text above.
- At most {max_points} points, most important first, one sentence each.
- Keep important names, numbers and dates exactly as written.
- Do not add anything that is not in the text.
- {rule}""",
        expected_output=f"A numbered list of at most {max_points} main points.",
        agent=extractor)

    t_format = Task(
        description=f"""Turn the points from the previous task into a clean Markdown summary:
1. "TL;DR" — 1-2 sentences at the top
2. The points grouped under 2-4 short headings, as bullet points
3. "Key takeaways" — at most 3 bullets
Do not add new information. {rule}""",
        expected_output="A Markdown summary with TL;DR, grouped bullet points, and key takeaways.",
        agent=formatter, context=[t_extract])

    result = run_crew([extractor, formatter], [t_extract, t_format])
    save_output("quick_summary", result, s)


# ==========================================
# Mode E: อ่านและอธิบายไฟล์ (อ่านทีละส่วน → สังเคราะห์)
# ==========================================
def run_mode_e():
    print("\n==========================================")
    print(" Mode E: อ่านและอธิบายไฟล์")
    print("==========================================")
    path = input("📁 พิมพ์ชื่อหรือพาธไฟล์ (ไฟล์ข้อความ/โค้ด หรือ PDF): ").strip().strip('"')
    if not path:
        return
    if not os.path.isfile(path):
        print(f"❌ ไม่พบไฟล์ '{path}' หรือพาธนี้ไม่ใช่ไฟล์")
        return

    print(f"📄 กำลังอ่านไฟล์ {path}...")
    try:
        content = read_document(path)
    except ValueError as ex:
        print(f"❌ {ex}")
        return
    if not content.strip():
        print(f"❌ ไม่พบข้อความที่อ่านได้ในไฟล์ '{path}'")
        return

    s = get_runtime_settings()
    llm = make_llm(s, temperature=0.2)
    kind = "code" if os.path.splitext(path)[1].lower() in CODE_EXTS else "document"
    material = condense(content, llm, s, kind)
    is_notes = material is not content
    source_label = ("notes taken while reading the file part by part" if is_notes
                    else "the full content of the file")

    if kind == "code":
        sections = """1. Purpose — what this file/program is for
2. Structure — main parts, functions and classes (use exact names) and what each does
3. How it works — the execution flow step by step, from the entry point
4. Inputs, outputs and dependencies (libraries, files, services)
5. Notes — possible bugs, risks or things to watch out for (only if visible in the code)"""
    else:
        sections = """1. What this file is (type, topic, purpose)
2. Main content, section by section
3. Important details (names, numbers, definitions)
4. Conclusion / key takeaway"""

    explainer = make_agent(
        "File Explainer",
        "Explain a file clearly and accurately, based only on what is actually in it.",
        "You are an expert at reading code and documents and explaining them to others.", llm)

    t_explain = Task(
        description=f"""File: "{os.path.basename(path)}"
Below is {source_label}:
<file>
{material}
</file>

Explain this file using exactly these sections:
{sections}

Rules:
- Only state what is supported by the content above; if something cannot be determined, say so.
- {detail_rule(s)}
- {lang_rule(s)}""",
        expected_output="An explanation of the file organized under the listed sections.",
        agent=explainer)

    result = run_crew([explainer], [t_explain])
    save_output("file_explanation", result, s)


# ==========================================
# Main Menu
# ==========================================
MODES = {"A": run_mode_a, "B": run_mode_b, "C": run_mode_c, "D": run_mode_d, "E": run_mode_e}

if __name__ == "__main__":
    while True:
        print("\n==========================================")
        print("       MAIN MENU: เลือกโหมดการทำงาน AI          ")
        print("==========================================")
        print("  [A] Mode A: แชทสนทนากับ AI อิสระ")
        print("  [B] Mode B: ผู้ช่วยเขียนโค้ด & DevOps (4 Sub-Agents)")
        print("  [C] Mode C: อ่านและวิเคราะห์ไฟล์ PDF (4 Sub-Agents)")
        print("  [D] Mode D: สรุปข้อความยาวแบบด่วน (2 Sub-Agents)")
        print("  [E] Mode E: อ่านและอธิบายไฟล์")
        print("  [X] ออกจากโปรแกรม (Exit)")

        choice = input("👉 เลือกโหมด (A, B, C, D, E หรือ X): ").strip().upper()
        if choice == "X":
            print("👋 ขอบคุณที่ใช้งานระบบ Local AI ครับ!")
            break
        if choice not in MODES:
            print("❌ กรุณาเลือกเฉพาะ A, B, C, D, E หรือ X เท่านั้นครับ")
            continue
        try:
            MODES[choice]()
        except KeyboardInterrupt:
            print("\n⏹️ ยกเลิกงาน กลับเมนูหลัก")
        except Exception as ex:
            print(f"\n❌ เกิดข้อผิดพลาด: {ex}")
            print(f"   ตรวจว่า Ollama รันอยู่ที่ {OLLAMA_URL} และ pull โมเดลไว้แล้ว (ollama list)")