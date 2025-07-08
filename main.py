<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>SceneCraft AI</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --main-bg: #f9fafb;
      --card-bg: #ffffff;
      --accent: #4c8eda;
      --accent-dark: #3b74b0;
      --text-dark: #222;
      --text-muted: #666;
      --border: #e2e8f0;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      font-family: 'Inter', sans-serif;
      background-color: var(--main-bg);
      color: var(--text-dark);
      padding: 20px;
    }
    .container {
      max-width: 900px;
      margin: auto;
    }
    h1 {
      text-align: center;
      font-size: 2.4rem;
      font-weight: 600;
      margin-bottom: 0.2rem;
      color: var(--accent-dark);
    }
    .subtitle {
      text-align: center;
      font-size: 1rem;
      color: var(--text-muted);
      margin-bottom: 2rem;
    }
    textarea, input {
      width: 100%;
      padding: 14px;
      margin-bottom: 16px;
      font-size: 1rem;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--card-bg);
      box-shadow: 0 0 0 2px transparent;
      transition: box-shadow 0.2s ease-in-out;
    }
    textarea:focus, input:focus {
      outline: none;
      box-shadow: 0 0 0 2px var(--accent);
    }
    button {
      width: 100%;
      padding: 14px;
      font-size: 1rem;
      font-weight: 600;
      background-color: var(--accent);
      color: white;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      transition: background-color 0.2s ease;
    }
    button:hover {
      background-color: var(--accent-dark);
    }
    button:disabled {
      background-color: #a0c4ee;
      cursor: not-allowed;
    }
    .output {
      white-space: pre-wrap;
      background-color: var(--card-bg);
      padding: 20px;
      border-radius: 8px;
      margin-top: 30px;
      border: 1px solid var(--border);
      box-shadow: 0 2px 4px rgba(0,0,0,0.03);
      font-size: 0.95rem;
      line-height: 1.6;
    }
    .footer {
      margin-top: 50px;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.85rem;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🎬 SceneCraft AI</h1>
    <p class="subtitle">Cinematic scene analysis built for studios, screenwriters & creatives</p>

    <textarea id="sceneInput" placeholder="Paste your scene, dialogue, or script excerpt here..."></textarea>
    <input type="password" id="tokenInput" placeholder="Enter your access token" />

    <button onclick="analyzeScene()" id="analyzeBtn">Analyze Scene</button>

    <div class="output" id="outputBox" style="display:none;"></div>

    <p class="footer">© 2025 SceneCraft. Built with cinematic intelligence 🎥</p>
  </div>

  <script>
    async function analyzeScene() {
      const scene = document.getElementById("sceneInput").value.trim();
      const token = document.getElementById("tokenInput").value.trim();
      const output = document.getElementById("outputBox");
      const button = document.getElementById("analyzeBtn");

      if (!token) {
        alert("Access token required.");
        return;
      }
      if (scene.length < 30) {
        alert("Please input a valid cinematic excerpt.");
        return;
      }

      output.style.display = "block";
      output.textContent = "🔍 Analyzing your scene, please wait...";
      button.disabled = true;

      try {
        const res = await fetch("https://screencraft-backend.onrender.com/analyze", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token
          },
          body: JSON.stringify({ scene })
        });

        const data = await res.json();
        if (res.ok && data.analysis) {
          output.textContent = data.analysis;
        } else {
          output.textContent = data.error || "❌ Failed to analyze. Please try again.";
        }
      } catch (err) {
        output.textContent = "🚨 Server error. Please try again later.";
      } finally {
        button.disabled = false;
      }
    }
  </script>
</body>
</html>
