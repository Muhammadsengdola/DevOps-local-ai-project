# Local AI Assistant (CrewAI + Ollama)

คู่มือนี้ใช้รันโปรเจกต์ผ่าน Docker Compose จาก Terminal ใน VS Code
ไม่ต้องเชื่อม MCP กับ Continue และไม่ต้องเรียก AI ผ่าน Continue

## ภาพรวมการทำงาน

```text
VS Code Terminal -> แอป Python / CrewAI ใน Docker Compose -> Ollama ใน Docker Compose -> Qwen
```

ใช้ Continue เป็น editor ได้ตามปกติ แต่การสั่งงาน AI ของโปรเจกต์นี้ทำใน Terminal
ด้วย `crew_pdf_4agents.py` เท่านั้น

## สิ่งที่ต้องติดตั้ง

- Windows 10/11, macOS หรือ Linux
- Docker Desktop หรือ Docker Engine พร้อม Docker Compose
- Visual Studio Code (ไม่บังคับ)

## รันแอป Python ใน Docker

ใช้ Docker Compose เพื่อเชื่อมแอป Python กับ Ollama โดย Compose จะดาวน์โหลดโมเดลทั้งสองรุ่น
ให้อัตโนมัติก่อนเปิดเมนูแอปในการใช้งานครั้งแรก โมเดลเก็บอยู่ใน volume ถาวรชื่อ `ollama_data`
เปิด Terminal ที่โฟลเดอร์โปรเจกต์ แล้ว build image และเปิดแอป:

```powershell
docker compose build
docker compose run --rm app
```

คำสั่งนี้จะเริ่ม Ollama, ดาวน์โหลด `qwen2.5:7b-instruct` และ `qwen2.5:14b-instruct`
ถ้ายังไม่มีใน volume แล้วจึงเปิดเมนูแอป การดาวน์โหลดครั้งแรกอาจใช้เวลานานและต้องมีพื้นที่ว่าง
เพียงพอ ครั้งต่อไปจะใช้โมเดลที่เก็บไว้แล้ว โฟลเดอร์โปรเจกต์ถูก mount ใน container
เพื่อให้อ่าน PDF และบันทึกผลลัพธ์ลงในเครื่องได้

พิมพ์ `X` ในเมนูเพื่อออกจากแอป จากนั้นหยุด Ollama ด้วย `docker compose down`
คำสั่งนี้ไม่ลบโมเดลใน volume หากต้องการเรียก Ollama จาก Windows โดยตรง พอร์ต `11434`
จะถูก publish ไว้ด้วย

## เมนูโปรแกรม

โปรแกรมจะแสดงเมนู:

- **A** — แชทกับ AI
- **B** — ช่วยเขียนโค้ดและตรวจแก้ด้วย 4 agents
- **C** — วิเคราะห์ PDF
- **D** — สรุปข้อความ
- **E** — อ่านและอธิบายไฟล์ข้อความ/โค้ด/PDF
- **X** — ออกจากโปรแกรม

เลือกโมเดล ภาษา รูปแบบบันทึก และระดับรายละเอียดตามคำถามบนหน้าจอ
งานที่ให้พิมพ์ข้อความหลายบรรทัด ให้พิมพ์ `END` ในบรรทัดใหม่เพื่อจบข้อความ

### ตัวอย่าง Mode E

1. เลือก `E`
2. ใส่ชื่อไฟล์ที่อยู่ในโฟลเดอร์โปรเจกต์ เช่น:

   ```text
   crew_pdf_4agents.py
   ```

   หรือใส่พาธเต็ม:

   ```text
   C:\Users\maste\Desktop\Dev Ops project\crew_pdf_4agents.py
   ```

3. เลือกโมเดลและภาษา
4. อ่านคำอธิบายที่แสดงใน Terminal

ไฟล์ PDF ที่เป็นภาพสแกนและไม่มีข้อความฝังอยู่จะต้องทำ OCR ก่อน โปรแกรมจะอ่านข้อความจาก PDF
ด้วยการดึงข้อความ ไม่ได้แปลงภาพเป็นข้อความให้อัตโนมัติ

## ตั้งค่า Ollama เพิ่มเติม (ไม่บังคับ)

ค่าเริ่มต้นของโปรแกรม:

- Ollama API: `http://localhost:11434`
- Context: `8192`
- ขนาดส่วนข้อความสำหรับเอกสารยาว: `6000` ตัวอักษร

เปลี่ยนค่าเฉพาะการรันแอปได้ เช่น:

```powershell
docker compose run --rm -e NUM_CTX=8192 -e CHUNK_CHARS=6000 app
```

โปรแกรมจะสร้างโมเดล Ollama สำเนาที่ลงท้ายด้วย `-ctx8192` ในการใช้งานครั้งแรก
เพื่อกำหนด context size ให้กับ Ollama โมเดลต้นฉบับจะยังคงอยู่

## ปิดโปรแกรมและหยุด Ollama

พิมพ์ `X` ในเมนูเพื่อออกจากโปรแกรม จากนั้นหยุด Compose services:

```powershell
docker compose down
```

โมเดลยังคงอยู่ใน Docker volume ชื่อ `ollama_data` แม้หยุด services แล้ว

## แก้ปัญหาเบื้องต้น

### `docker` ติดต่อ Docker ไม่ได้

- เปิด Docker Desktop และรอให้สถานะพร้อม
- ตรวจสอบด้วย `docker info`

### `connection refused` หรือเรียก `localhost:11434` ไม่ได้

- ตรวจว่า services ทำงานด้วย `docker compose ps`
- เปิด services และให้ Compose เตรียมโมเดลด้วย `docker compose run --rm app`
- ตรวจ API ด้วย `Invoke-RestMethod http://localhost:11434/api/tags`

### แจ้งว่าไม่พบโมเดล

Compose จะดาวน์โหลดโมเดลที่กำหนดไว้โดยอัตโนมัติเมื่อรันแอป หากดาวน์โหลดไม่สำเร็จ
ให้ตรวจ logs ด้วย `docker compose logs ollama-models`

### `ModuleNotFoundError`

ลอง build image ใหม่ด้วย `docker compose build --no-cache app`

### โปรแกรมตอบช้า

- เริ่มจาก `qwen2.5:7b-instruct`
- การประมวลผลครั้งแรกอาจช้ากว่า เพราะ Ollama ต้องโหลดโมเดล
- ไฟล์ยาวจะถูกแบ่งเป็นส่วนและวิเคราะห์หลายรอบ

## MCP และ Continue

การรันแอปผ่าน Compose ไม่จำเป็นต้องใช้ MCP แต่สามารถเชื่อม Continue Agent
กับ MCP server ของโปรเจกต์เพื่อเรียกเครื่องมือ `explain_file` ได้ โดย server จะอ่าน
ได้เฉพาะไฟล์ภายในโฟลเดอร์โปรเจกต์ และใช้ Ollama ตามการตั้งค่าของโปรแกรม

Continue สามารถเปิด MCP server ผ่าน Docker Compose ได้ โดยไม่ต้องติดตั้ง Python
หรือ dependencies บนเครื่อง ให้เพิ่ม config ต่อไปนี้ใน
`C:\Users\<ชื่อผู้ใช้>\.continue\config.yaml` และแทน `C:\path\to\project`
ด้วยพาธจริงของโฟลเดอร์โปรเจกต์:

```yaml
mcpServers:
  - name: CrewAI Local
    command: docker
    args:
      - compose
      - -f
      - 'C:\path\to\project\compose.yaml'
      - run
      - --rm
      - -T
      - -e
      - WORKSPACE_ROOT=/app
      - -e
      - CREW_VERBOSE=0
      - app
      - python
      - -u
      - mcp_server.py
```

Docker ต้องทำงานอยู่ก่อนเริ่ม Continue จากนั้นเริ่ม Continue ใหม่ เครื่องมือรับพาธไฟล์แบบ relative ต่อโฟลเดอร์โปรเจกต์
และเลือกภาษา `Thai` หรือ `English` กับระดับรายละเอียด `short` หรือ `detailed` ได้
การเรียก MCP ต้องมี Ollama ทำงานและมีโมเดล Qwen ที่ต้องการอยู่ในเครื่องแล้ว