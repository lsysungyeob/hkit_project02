from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import csv, os, tempfile, re
from datetime import datetime
from gtts import gTTS
import whisper

app = FastAPI()

survey_q = [
    "어떤 일의 어려운 부분은 끝내 놓고, 그 일을 마무리를 짓지 못해 곤란을 겪은 적이 있습니까?",
    "체계가 필요한 일을 해야 할 때 순서대로 진행하기 어려운 경우가 있습니까?",
    "약속이나 해야 할 일을 잊어버려 곤란을 겪은 적이 있습니까?",
    "골치 아픈 일은 피하거나 미루는 경우가 있습니까?",
    "오래 앉아 있을 때, 손을 만지작거리거나 발을 꼼지락거리는 경우가 있습니까?",
    "마치 모터가 달린 것처럼, 과도하게 혹은 멈출 수 없이 활동을 하는 경우가 있습니까?",
    "지루하고 어려운 일을 할 때, 부주의해서 실수를 하는 경우가 있습니까?",
    "지루하고 반복적인 일을 할 때, 주의 집중이 힘든 경우가 있습니까?",
    "대화 중, 특히 상대방이 당신에게 직접적으로 말하고 있을 때에도, 집중하기 힘든 경우가 있습니까?",
    "집이나 직장에서 물건을 엉뚱한 곳에 두거나 어디에 두었는지 찾기 어려운 경우가 있습니까?",
    "주변에서 벌어지는 일이나 소음 때문에 주의가 산만해 지는 경우가 있습니까?",
    "회의나 다른 사회적 상황에서 계속 앉아 있어야 함에도 잠깐씩 자리를 뜨는 경우가 있습니까?",
    "안절부절 못하거나 조바심하는 경우가 있습니까?",
    "혼자 쉬고 있을 때, 긴장을 풀거나 마음을 편하게 갖기 어려운 경우가 있습니까?",
    "사회적 상황에서 나 혼자 말을 너무 많이 한다고 느끼는 경우가 있습니까?",
    "대화 도중 상대방이 말을 끝내기 전에 끼어들어 상대방의 말을 끊는 경우가 있습니까?",
    "차례를 지켜야 하는 상황에서 자신의 차례를 기다리는 것이 어려운 경우가 있습니까?",
    "다른 사람이 바쁘게 일할 때, 방해되는 행동을 하는 경우가 있습니까?",
]

survey_a = [
    "1. 전혀 그렇지 않다",
    "2. 거의 그렇지 않다",
    "3. 약간 혹은 가끔 그렇다",
    "4. 자주 그렇다",
    "5. 매우 자주 그렇다"
]

os.makedirs("static/audio", exist_ok=True)
for i, q in enumerate(survey_q):
    path = f"static/audio/q{i+1}.wav"
    if not os.path.exists(path):
        gTTS(q, lang="ko").save(path)

model = whisper.load_model("base")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def survey_page():
    html = """
    <!DOCTYPE html>
    <html lang='ko'>
    <head>
      <meta charset='UTF-8'>
      <title>ADHD 설문지</title>
      <style>
        .question-block { margin-bottom: 2em; }
        .answers { display: flex; gap: 1em; margin-top: 0.5em; flex-wrap: wrap; }
        .answers label {
          border: 1px solid #ccc; border-radius: 6px;
          padding: 0.5em 1em; cursor: pointer;
          transition: background 0.3s;
        }
        .highlight { background-color: lightblue !important; font-weight: bold; }
        .button {
          font-size: 0.8em;
          padding: 0.5em 0.6em;
          border-radius: 8px;
          margin: 0.2em 0.2em 0.2em 0;
          cursor: pointer;
        }
        #volume-bar {
          width: 100%; height: 20px; display: none; margin-bottom: 1em;
        }
        #volume-bar::-webkit-progress-value { background-color: #4caf50; }
        #volume-bar::-moz-progress-bar { background-color: #4caf50; }
      </style>
    </head>
    <body>
      <h1>ADHD 자가설문지</h1>
      <p><strong>지난 6개월 동안의 행동을 기준으로 응답해 주세요.</strong></p>
      <p><strong>질문을 들으려면 [듣기], 음성 응답은 [응답]을 누르세요.</strong></p>

      <progress id="volume-bar" max="255" value="0"></progress>

      <form method='post' action='/submit' onsubmit='return validateForm();'>
        <label>이름: <input type='text' name='name' required></label>
        <hr>
    """
    for i, q in enumerate(survey_q):
        html += f"<div class='question-block' id='qblock{i}'>"
        html += f"<p><strong>{i+1}. {q}</strong> <button type='button' class='button' onclick='playAudio({i+1})'>듣기</button> <button type='button' class='button' onclick='startRecording({i})'>응답</button></p><div class='answers' id='answer-row-{i}'>"
        for j, a in enumerate(survey_a, 1):
            html += f"<input type='radio' id='q{i}_{j}' name='q{i}' value='{j}' hidden>"
            html += f"<label for='q{i}_{j}' id='label-q{i}-{j}'>{a}</label>"
        html += "</div></div>"
    html += "<button type='submit' class='button'>제출</button></form><audio id='player' hidden></audio>"

    html += """
    <script>
      document.addEventListener("DOMContentLoaded", () => {
        function playAudio(q) {
          document.getElementById('player').src = "/static/audio/q" + q + ".wav";
          document.getElementById('player').play();
        }

        function startRecording(qIndex) {
          navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
            const mediaRecorder = new MediaRecorder(stream);
            let chunks = [];

            mediaRecorder.ondataavailable = e => chunks.push(e.data);

            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContext.createMediaStreamSource(stream);
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            const dataArray = new Uint8Array(analyser.frequencyBinCount);
            source.connect(analyser);

            const volumeBar = document.getElementById("volume-bar");
            volumeBar.style.display = "block";

            let rafId;
            function updateVolume() {
              analyser.getByteFrequencyData(dataArray);
              const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
              volumeBar.value = avg;
              rafId = requestAnimationFrame(updateVolume);
            }
            updateVolume();

            mediaRecorder.onstop = () => {
              cancelAnimationFrame(rafId);
              volumeBar.style.display = "none";

              const blob = new Blob(chunks, { type: "audio/wav" });
              const formData = new FormData();
              formData.append("file", blob, "recorded.wav");

              fetch("/recognize", {
                method: "POST",
                body: formData
              }).then(res => res.json()).then(data => {
                if (data.number) {
                  const radio = document.querySelector(`input[name='q${qIndex}'][value='${data.number}']`);
                  if (radio) {
                    radio.checked = true;
                    document.querySelector(`#label-q${qIndex}-${data.number}`).classList.add("highlight");
                  }
                } else {
                  alert(`문항 ${qIndex + 1}: 음성을 인식하지 못했습니다. 다시 시도해주세요.`);
                }
              });

              stream.getTracks().forEach(t => t.stop());
              audioContext.close();
            };

            mediaRecorder.start();
            setTimeout(() => mediaRecorder.stop(), 3000);
          });
        }

        document.querySelectorAll(".answers label").forEach(label => {
          label.addEventListener("click", () => {
            const [qname, value] = label.htmlFor.split("_");
            const radio = document.getElementById(`${qname}_${value}`);
            if (radio) radio.checked = true;
            document.querySelectorAll(`input[name='${qname}']`).forEach(r => {
              document.querySelector(`#label-${qname}-${r.value}`)?.classList.remove("highlight");
            });
            label.classList.add("highlight");
          });
        });

        window.validateForm = function () {
          const name = document.querySelector("input[name='name']").value.trim();
          if (!name) {
            alert("이름을 입력해주세요.");
            return false;
          }
          const total = document.querySelectorAll(".question-block").length;
          for (let i = 0; i < total; i++) {
            if (!document.querySelector(`input[name='q${i}']:checked`)) {
              alert(`문항 ${i + 1}에 응답하지 않았습니다.`);
              return false;
            }
          }
          return true;
        };

        window.playAudio = playAudio;
        window.startRecording = startRecording;
      });
    </script>
    </body></html>"""
    return HTMLResponse(content=html)

@app.post("/submit", response_class=HTMLResponse)
async def submit(request: Request):
    form = await request.form()
    name = form.get("name", "").strip()
    responses = {k: v for k, v in form.items() if k.startswith("q")}

    if not name or len(responses) != len(survey_q):
        return HTMLResponse("<script>alert('모든 문항에 응답하고 이름을 입력해야 합니다.'); window.location.href = '/';</script>")

    scores = [int(responses[f"q{i}"]) for i in range(len(survey_q))]

    file_exists = os.path.exists("survey_results.csv")
    with open("survey_results.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["이름"] + [f"Q{i+1}" for i in range(len(scores))] + ["제출시각"])
        writer.writerow([name] + scores + [datetime.now().isoformat()])

    html = f"""
    <!DOCTYPE html>
    <html lang='ko'>
    <head><meta charset='UTF-8'><title>설문 결과</title>
    <style>
      .button {{
        font-size: 0.8em;
        padding: 0.5em 0.6em;
        border-radius: 8px;
        margin: 0.2em;
        cursor: pointer;
      }}
    </style></head>
    <body><h2>{name}님의 설문 응답 결과</h2><ul>
    """
    html += "".join([f"<li>문항 {i+1}: {s}점</li>" for i, s in enumerate(scores)])
    html += "</ul><form method='get' action='/'><button type='submit' class='button'>처음으로</button></form></body></html>"
    return HTMLResponse(content=html)

@app.post("/recognize")
async def recognize_audio(file: UploadFile):
    audio_bytes = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        result = model.transcribe(tmp.name, language="ko")
        text = result["text"]
        print(text)
    match = re.search(r"\b([1-5])\b", text)
    return { "text": text, "number": int(match.group(1)) if match else None }
