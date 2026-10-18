# Local AI Assistant (CrewAI + Ollama)

คู่มือนี้ใช้รันโปรเจกต์ผ่าน Terminal ใน VS Code โดยให้ Ollama ทำงานใน Docker
ไม่ต้องเชื่อม MCP กับ Continue และไม่ต้องเรียก AI ผ่าน Continue

## ภาพรวมการทำงาน

```text
VS Code Terminal -> Python / CrewAI -> Ollama API -> Ollama ใน Docker -> Qwen
```

ใช้ Continue เป็น editor ได้ตามปกติ แต่การสั่งงาน AI ของโปรเจกต์นี้ทำใน Terminal
ด้วย `crew_pdf_4agents.py` เท่านั้น

## สิ่งที่ต้องติดตั้ง

- Windows 10/11
- Docker Desktop (ติดตั้งแล้วและเปิดทำงาน)
- Python 3.10
- Visual Studio Code

## เริ่มใช้งานแบบกดครั้งเดียว (Windows)

เมื่อมี Docker Desktop และ Python 3.10 แล้ว ให้ดับเบิลคลิกไฟล์
[`setup_and_run.bat`](./setup_and_run.bat) ในโฟลเดอร์โปรเจกต์ หรือเปิด Terminal ใน VS Code
ที่โฟลเดอร์โปรเจกต์แล้วสั่ง:

```powershell
.\setup_and_run.bat
```

สคริปต์จะทำงานตามลำดับ:

1. สร้าง `.venv` ด้วย Python 3.10 ถ้ายังไม่มี
2. ติดตั้งแพ็กเกจตาม `requirements.txt`
3. เริ่ม container ชื่อ `ollama` ถ้ามีอยู่แล้วจะเริ่ม container เดิม
   ถ้ายังไม่มีจะดาวน์โหลด Ollama image และสร้าง container พร้อม volume เก็บโมเดล
4. ดาวน์โหลด `qwen2.5:14b-instruct` และ `qwen2.5:7b-instruct` เฉพาะรุ่นที่ยังไม่มี
5. เปิดเมนู `crew_pdf_4agents.py` ในหน้าต่างเดียวกัน

ครั้งแรกอาจใช้เวลานาน เพราะต้องติดตั้ง Python packages และดาวน์โหลดโมเดลทั้งสองรุ่น
ควรมีพื้นที่ว่างอย่างน้อยประมาณ 15 GB สำหรับโมเดลทั้งสอง (อาจมากกว่านี้ตามรุ่นและ
การตั้งค่า context) และเวลาที่ใช้ขึ้นกับความเร็วอินเทอร์เน็ต ครั้งถัดไปจะข้ามการดาวน์โหลด
โมเดลที่มีอยู่แล้ว

สคริปต์นี้ไม่ได้ติดตั้ง Docker Desktop หรือ Python ให้อัตโนมัติ ต้องติดตั้งสองอย่างนี้ก่อน
และต้องเปิด Docker Desktop ให้พร้อมก่อนเริ่ม สคริปต์ไม่ลบ virtual environment, container
หรือ volume เดิม หากพบ `.venv` ที่ไม่ได้ใช้ Python 3.10 จะหยุดและแจ้งเตือน

หากไม่ต้องการใช้สคริปต์ตั้งค่า ให้ทำตามขั้นตอน Manual ด้านล่างต่อได้

## Manual: 1. เริ่ม Ollama ใน Docker

เปิด Docker Desktop และรอให้ Docker ทำงาน จากนั้นเปิด PowerShell หรือ VS Code Terminal
ตรวจสอบการเชื่อมต่อ:

```powershell
docker info
```

สร้างและเริ่ม Ollama container พร้อม volume สำหรับเก็บโมเดล:

```powershell
docker run -d --name ollama --restart unless-stopped -p 11434:11434 -v ollama:/root/.ollama ollama/ollama
```

ถ้าขึ้นว่า container ชื่อ `ollama` มีอยู่แล้ว ให้เริ่ม container เดิมแทน:

```powershell
docker start ollama
```

ตรวจว่า container กำลังทำงาน:

```powershell
docker ps
```

## Manual: 2. ดาวน์โหลดโมเดล Qwen

แนะนำเริ่มด้วย 7B ก่อน เพราะใช้ทรัพยากรน้อยกว่า:

```powershell
docker exec -it ollama ollama pull qwen2.5:7b-instruct
```

ถ้าต้องการโมเดล 14B และเครื่องมีทรัพยากรเพียงพอ:

```powershell
docker exec -it ollama ollama pull qwen2.5:14b-instruct
```

ตรวจว่าโมเดลดาวน์โหลดแล้ว:

```powershell
docker exec -it ollama ollama list
```

ทดสอบ Ollama จาก Windows:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
```

ควรได้รายการโมเดลตอบกลับมา พอร์ต `11434` เป็น API ที่โปรแกรม Python ใช้ติดต่อกับ Ollama

## Manual: 3. เปิดโฟลเดอร์โปรเจกต์ใน VS Code

ใน VS Code เลือก **File > Open Folder...** แล้วเปิดโฟลเดอร์โปรเจกต์
จากนั้นเลือก **Terminal > New Terminal** และเข้าโฟลเดอร์โปรเจกต์:

```powershell
cd "C:\Users\maste\Desktop\Dev Ops project"
```

ตรวจว่า Terminal อยู่ในโฟลเดอร์เดียวกับ `crew_pdf_4agents.py` และ `requirements.txt`:

```powershell
Get-Location
Get-ChildItem
```

## Manual: 4. เตรียม Python environment

สร้าง virtual environment (ทำครั้งแรกครั้งเดียว):

```powershell
py -3.10 -m venv .venv
```

เปิดใช้งาน environment ใน PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

ถ้า PowerShell ไม่อนุญาตให้รัน `Activate.ps1` ไม่ต้องเปลี่ยน Execution Policy:
ใช้ Python จาก virtual environment โดยระบุพาธเต็มตามตัวอย่างในหัวข้อถัดไปแทนได้

ติดตั้ง dependencies จากไฟล์ requirements:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

คำสั่งติดตั้งอาจใช้เวลาสักครู่ เมื่อเห็น `Successfully installed` หรือแจ้งว่า
ติดตั้ง requirements ครบแล้ว จึงไปขั้นตอนถัดไป

## Manual: 5. รันโปรแกรมผ่าน Terminal

ถ้าเปิดใช้งาน virtual environment แล้ว:

```powershell
python .\crew_pdf_4agents.py
```

ถ้าไม่ได้ Activate environment ให้เรียก Python ใน `.venv` โดยตรง:

```powershell
.\.venv\Scripts\python.exe .\crew_pdf_4agents.py
```

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

เปลี่ยนค่าเฉพาะ Terminal ปัจจุบันได้ เช่น:

```powershell
$env:OLLAMA_URL = "http://localhost:11434"
$env:NUM_CTX = "8192"
$env:CHUNK_CHARS = "6000"
python .\crew_pdf_4agents.py
```

โปรแกรมจะสร้างโมเดล Ollama สำเนาที่ลงท้ายด้วย `-ctx8192` ในการใช้งานครั้งแรก
เพื่อกำหนด context size ให้กับ Ollama โมเดลต้นฉบับจะยังคงอยู่

## ปิดโปรแกรมและหยุด Ollama

พิมพ์ `X` ในเมนูเพื่อออกจากโปรแกรม การปิดโปรแกรมไม่ได้หยุด Ollama container
ถ้าต้องการหยุด Ollama ด้วยตนเอง:

```powershell
docker stop ollama
```

เริ่มใช้อีกครั้ง:

```powershell
docker start ollama
```

โมเดลยังคงอยู่ใน Docker volume ชื่อ `ollama` แม้หยุด container แล้ว

## แก้ปัญหาเบื้องต้น

### `docker` ติดต่อ Docker ไม่ได้

- เปิด Docker Desktop และรอให้สถานะพร้อม
- ตรวจสอบด้วย `docker info`

### `connection refused` หรือเรียก `localhost:11434` ไม่ได้

- ตรวจว่า container ทำงานด้วย `docker ps`
- ถ้าไม่ทำงาน ให้ใช้ `docker start ollama`
- ตรวจ API ด้วย `Invoke-RestMethod http://localhost:11434/api/tags`

### แจ้งว่าไม่พบโมเดล

```powershell
docker exec -it ollama ollama list
```

ถ้าไม่มีโมเดลที่เลือก ให้ดาวน์โหลด เช่น:

```powershell
docker exec -it ollama ollama pull qwen2.5:7b-instruct
```

### `ModuleNotFoundError`

ตรวจว่าใช้ Python ใน `.venv` และติดตั้ง requirements แล้ว:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### โปรแกรมตอบช้า

- เริ่มจาก `qwen2.5:7b-instruct`
- การประมวลผลครั้งแรกอาจช้ากว่า เพราะ Ollama ต้องโหลดโมเดล
- ไฟล์ยาวจะถูกแบ่งเป็นส่วนและวิเคราะห์หลายรอบ

## MCP และ Continue

การรันโปรแกรมจาก Terminal ยังไม่จำเป็นต้องใช้ MCP แต่สามารถเชื่อม Continue Agent
กับ MCP server ของโปรเจกต์เพื่อเรียกเครื่องมือ `explain_file` ได้ โดย server จะอ่าน
ได้เฉพาะไฟล์ภายในโฟลเดอร์โปรเจกต์ และใช้ Ollama ตามการตั้งค่าของโปรแกรม

หลังติดตั้ง dependencies และเตรียม Ollama ตามขั้นตอนด้านบน ให้เพิ่ม MCP server
ต่อไปนี้ใน Continue config ที่ `C:\Users\<ชื่อผู้ใช้>\.continue\config.yaml`
โดยแทน `C:\path\to\project` ด้วยพาธจริงของโฟลเดอร์โปรเจกต์:

```yaml
mcpServers:
  - name: CrewAI Local
    command: 'C:\path\to\project\.venv\Scripts\python.exe'
    args:
      - 'C:\path\to\project\mcp_server.py'
    env:
      WORKSPACE_ROOT: 'C:\path\to\project'
      CREW_VERBOSE: '0'
```

จากนั้นเริ่ม Continue ใหม่ เครื่องมือรับพาธไฟล์แบบ relative ต่อโฟลเดอร์โปรเจกต์
และเลือกภาษา `Thai` หรือ `English` กับระดับรายละเอียด `short` หรือ `detailed` ได้
การเรียก MCP ต้องมี Ollama ทำงานและมีโมเดล Qwen ที่ต้องการอยู่ในเครื่องแล้ว
