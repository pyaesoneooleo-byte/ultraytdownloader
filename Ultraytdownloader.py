from flask import Flask, request, jsonify, send_file, render_template_string
import yt_dlp
import os
import uuid
import threading
import traceback
import re

app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

download_progress = {}

# ==========================================
# FRONTEND: HTML + Tailwind CSS (UI Design)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ultra Downloader</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: 'Inter', sans-serif; }
        .glass-panel { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
        .gradient-text { background: linear-gradient(to right, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .gradient-btn { background: linear-gradient(to right, #3b82f6, #6366f1); transition: all 0.3s ease; }
        .gradient-btn:hover { background: linear-gradient(to right, #2563eb, #4f46e5); transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.4); }
        .spinner { border: 4px solid rgba(255, 255, 255, 0.1); border-left-color: #38bdf8; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; display: inline-block; vertical-align: middle; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="min-h-screen flex flex-col items-center py-12 px-4">

    <div class="text-center max-w-2xl w-full mb-10">
        <h1 class="text-4xl md:text-5xl font-extrabold mb-4"><i class="fa-brands fa-youtube text-red-500 mr-2"></i>Ultra <span class="gradient-text">Downloader</span></h1>
        <p class="text-slate-400 text-lg">Download YouTube Videos & Audio in High Quality.</p>
    </div>

    <div class="glass-panel rounded-2xl p-6 max-w-3xl w-full shadow-2xl mb-8">
        <div class="flex flex-col md:flex-row gap-4">
            <input type="text" id="urlInput" placeholder="Paste YouTube link here (e.g., https://youtu.be/...)" 
                   class="flex-1 bg-slate-800 text-white border border-slate-600 rounded-lg px-5 py-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-lg">
            <button id="fetchBtn" onclick="fetchVideoInfo()" class="gradient-btn text-white font-bold rounded-lg px-8 py-4 text-lg flex items-center justify-center min-w-[160px]">
                <span id="btnText">Fetch Links</span>
                <i id="btnIcon" class="fa-solid fa-arrow-right ml-2"></i>
                <div id="btnSpinner" class="spinner ml-2 hidden"></div>
            </button>
        </div>
        
        <div class="mt-4 flex justify-end hidden" id="clearBtnContainer">
            <button onclick="location.reload()" class="bg-slate-700 hover:bg-slate-600 text-white py-2 px-4 rounded-lg text-sm transition flex items-center">
                <i class="fa-solid fa-rotate-right mr-2"></i> အသစ်ပြန်စမည် (Clear)
            </button>
        </div>
        <p id="errorMsg" class="text-red-400 mt-3 hidden text-center font-medium"></p>
    </div>

    <div id="resultSection" class="glass-panel rounded-2xl p-6 max-w-3xl w-full shadow-2xl hidden mb-8">
        <div class="flex flex-col md:flex-row gap-6 items-start">
            <div class="w-full md:w-1/3">
                <img id="thumbImg" src="" alt="Thumbnail" class="w-full rounded-xl shadow-lg">
                <div class="mt-3 text-center">
                    <span id="durationBadge" class="bg-slate-700 text-xs px-3 py-1 rounded-full text-slate-300 font-medium"></span>
                </div>
            </div>
            
            <div class="w-full md:w-2/3">
                <h2 id="videoTitle" class="text-xl md:text-2xl font-bold mb-4 line-clamp-2 text-white"></h2>
                
                <div class="space-y-4 mt-6">
                    <div>
                        <h3 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3"><i class="fa-solid fa-video mr-2"></i>Video Downloads</h3>
                        <div class="grid grid-cols-2 gap-3" id="videoOptions"></div>
                    </div>
                    
                    <div class="pt-4 border-t border-slate-700">
                        <h3 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3"><i class="fa-solid fa-music mr-2"></i>Audio Downloads</h3>
                        <div class="grid grid-cols-2 gap-3" id="audioOptions"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Processing & Download Status Overlay with Progress -->
    <div id="downloadStatus" class="fixed bottom-5 right-5 glass-panel p-5 rounded-xl shadow-2xl hidden border-l-4 border-blue-500 z-50 transition-all min-w-[300px]">
        <div class="flex items-center gap-4">
            <div class="spinner"></div>
            <div class="flex-1">
                <p class="font-bold text-white text-lg" id="statusTitle">Downloading...</p>
                <p class="text-sm text-slate-300" id="progressText">0% downloaded</p>
                <div class="w-full bg-slate-700 rounded-full h-2.5 mt-2">
                    <div id="progressBar" class="bg-blue-500 h-2.5 rounded-full" style="width: 0%"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function fetchVideoInfo() {
            const url = document.getElementById('urlInput').value.trim();
            const fetchBtn = document.getElementById('fetchBtn');
            const btnText = document.getElementById('btnText');
            const btnIcon = document.getElementById('btnIcon');
            const btnSpinner = document.getElementById('btnSpinner');
            const errorMsg = document.getElementById('errorMsg');
            const resultSection = document.getElementById('resultSection');
            const clearBtnContainer = document.getElementById('clearBtnContainer');

            if (!url) {
                errorMsg.innerText = "Please enter a valid YouTube link.";
                errorMsg.classList.remove('hidden');
                return;
            }

            errorMsg.classList.add('hidden');
            resultSection.classList.add('hidden');
            clearBtnContainer.classList.add('hidden');
            fetchBtn.disabled = true;
            btnText.innerText = "Fetching...";
            btnIcon.classList.add('hidden');
            btnSpinner.classList.remove('hidden');

            try {
                const response = await fetch('/api/info', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                
                const data = await response.json();

                if (response.ok) {
                    document.getElementById('thumbImg').src = data.thumbnail;
                    document.getElementById('videoTitle').innerText = data.title;
                    
                    const minutes = Math.floor(data.duration / 60);
                    const seconds = data.duration % 60;
                    document.getElementById('durationBadge').innerText = `⏱️ ${minutes}:${seconds.toString().padStart(2, '0')}`;

                    const videoContainer = document.getElementById('videoOptions');
                    videoContainer.innerHTML = '';
                    data.formats.video.forEach(fmt => {
                        const btn = document.createElement('button');
                        btn.className = "bg-slate-800 hover:bg-slate-700 text-white py-2 px-4 rounded-lg text-sm border border-slate-600 transition flex justify-between items-center";
                        btn.innerHTML = `<span>${fmt.resolution}</span> <i class="fa-solid fa-download text-slate-400"></i>`;
                        btn.onclick = () => startDownload(url, fmt.id, 'mp4');
                        videoContainer.appendChild(btn);
                    });

                    const audioContainer = document.getElementById('audioOptions');
                    audioContainer.innerHTML = '';
                    data.formats.audio.forEach(fmt => {
                        const btn = document.createElement('button');
                        btn.className = "bg-slate-800 hover:bg-slate-700 text-white py-2 px-4 rounded-lg text-sm border border-slate-600 transition flex justify-between items-center";
                        btn.innerHTML = `<span>${fmt.quality}</span> <i class="fa-solid fa-download text-slate-400"></i>`;
                        btn.onclick = () => startDownload(url, fmt.id, 'mp3');
                        audioContainer.appendChild(btn);
                    });

                    resultSection.classList.remove('hidden');
                    clearBtnContainer.classList.remove('hidden');
                } else {
                    errorMsg.innerText = data.error || "Failed to fetch video information.";
                    errorMsg.classList.remove('hidden');
                }
            } catch (err) {
                errorMsg.innerText = "Network error. Please try again.";
                errorMsg.classList.remove('hidden');
            } finally {
                fetchBtn.disabled = false;
                btnText.innerText = "Fetch Links";
                btnIcon.classList.remove('hidden');
                btnSpinner.classList.add('hidden');
            }
        }

        async function startDownload(url, quality_id, type) {
            const statusBox = document.getElementById('downloadStatus');
            const statusTitle = document.getElementById('statusTitle');
            const progressText = document.getElementById('progressText');
            const progressBar = document.getElementById('progressBar');
            
            statusBox.classList.remove('hidden');
            statusTitle.innerText = "Downloading...";
            progressText.innerText = "0%";
            progressBar.style.width = "0%";

            try {
                const response = await fetch(`/api/start-download?url=${encodeURIComponent(url)}&quality=${quality_id}&type=${type}`);
                const data = await response.json();

                if (!response.ok) {
                    alert(data.error || "Download failed");
                    statusBox.classList.add('hidden');
                    return;
                }

                const fileId = data.file_id;

                const interval = setInterval(async () => {
                    const progRes = await fetch(`/api/progress/${fileId}`);
                    const progData = await progRes.json();

                    if (progData.status === 'finished') {
                        clearInterval(interval);
                        statusTitle.innerText = "Processing Complete!";
                        progressText.innerText = "100%";
                        progressBar.style.width = "100%";

                        window.location.href = `/api/get-file/${fileId}`;

                        setTimeout(() => {
                            statusBox.classList.add('hidden');
                        }, 1000);

                    } else if (progData.status === 'error') {
                        clearInterval(interval);
                        statusTitle.innerText = "Download Error!";
                        progressText.innerText = progData.message || "Something went wrong";
                        setTimeout(() => { statusBox.classList.add('hidden'); }, 3000);
                    } else {
                        const percent = progData.percent || "0%";
                        progressText.innerText = percent;
                        progressBar.style.width = percent;
                        if(progData.status === 'processing') {
                            statusTitle.innerText = "Processing (Merging)...";
                        }
                    }
                }, 1000);

            } catch (err) {
                alert("Network error occurred.");
                statusBox.classList.add('hidden');
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/info', methods=['POST'])
def get_video_info():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400

    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                "title": info.get('title', 'Unknown Title'),
                "thumbnail": info.get('thumbnail', ''),
                "duration": info.get('duration', 0),
                "formats": {
                    "video": [
                        {"resolution": "1080p (MP4)", "id": "1080p"},
                        {"resolution": "720p (MP4)", "id": "720p"},
                        {"resolution": "480p (MP4)", "id": "480p"}
                    ],
                    "audio": [{"quality": "High Quality (MP3)", "id": "mp3_high"}]
                }
            })
    except Exception as e:
        return jsonify({"error": f"Extraction failed: {str(e)}"}), 500

def run_download(url, quality, dl_type, file_id):
    filepath_template = os.path.join(DOWNLOAD_FOLDER, f"{file_id}.%(ext)s")

    def progress_hook(d):
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%').strip()
            clean_p = re.sub(r'\x1b\[[0-9;]*m', '', p)
            download_progress[file_id] = {'status': 'downloading', 'percent': clean_p}
        elif d['status'] == 'finished':
            download_progress[file_id] = {'status': 'processing', 'percent': '100%'}

    if dl_type == 'mp4':
        # ဖိုင်မပျက်စေရန် MP4 format သက်သက်ကို တိကျစွာ ပေါင်းစပ်ပေးမည့် Format String
        if quality == '1080p':
            format_str = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif quality == '720p':
            format_str = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
        else:
            format_str = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
            
        ydl_opts = {
            'format': format_str,
            'outtmpl': filepath_template,
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
            'quiet': True
        }
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': filepath_template,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'progress_hooks': [progress_hook],
            'quiet': True
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        download_progress[file_id] = {'status': 'finished', 'percent': '100%'}
    except Exception as e:
        print(traceback.format_exc())
        download_progress[file_id] = {'status': 'error', 'message': str(e)}

@app.route('/api/start-download', methods=['GET'])
def start_download():
    url = request.args.get('url')
    quality = request.args.get('quality')
    dl_type = request.args.get('type')

    if not url or not quality:
        return jsonify({"error": "Missing parameters"}), 400

    file_id = uuid.uuid4().hex
    download_progress[file_id] = {'status': 'downloading', 'percent': '0%'}

    thread = threading.Thread(target=run_download, args=(url, quality, dl_type, file_id))
    thread.start()

    return jsonify({"file_id": file_id})

@app.route('/api/progress/<file_id>', methods=['GET'])
def get_progress(file_id):
    prog = download_progress.get(file_id, {'status': 'downloading', 'percent': '0%'})
    return jsonify(prog)

@app.route('/api/get-file/<file_id>', methods=['GET'])
def get_file(file_id):
    actual_file = None
    for filename in os.listdir(DOWNLOAD_FOLDER):
        if filename.startswith(file_id):
            actual_file = os.path.join(DOWNLOAD_FOLDER, filename)
            break

    if not actual_file or not os.path.exists(actual_file):
        return "File not found", 404

    as_attachment_name = os.path.basename(actual_file)
    mimetype = 'video/mp4' if actual_file.endswith('.mp4') else 'audio/mpeg'

    return send_file(actual_file, as_attachment=True, download_name=as_attachment_name, mimetype=mimetype)

if __name__ == '__main__':
    app.run(debug=True, port=5000)