<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SceneCraft AI</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {
      font-family: 'Segoe UI', sans-serif;
      background: linear-gradient(to right, #1e3a8a, #4f46e5);
    }
  </style>
</head>
<body class="text-gray-100">
  <div class="max-w-3xl mx-auto p-6">
    <div class="text-center mb-8">
      <h1 class="text-4xl font-extrabold text-yellow-400 mb-2">SceneCraft AI</h1>
      <p class="text-md text-indigo-100">Cinematic Scene Analyzer & Creative Mentor</p>
    </div>

    <textarea id="sceneInput" rows="8" placeholder="Paste your scene, script excerpt, dialogue or monologue here..."
      class="w-full p-4 border border-indigo-500 bg-indigo-900 placeholder-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-yellow-400 mb-4 text-gray-100"></textarea>

    <div class="flex flex-col gap-3 mb-4">
      <input type="password" id="tokenInput" placeholder="Enter access token here"
        class="w-full p-3 border border-yellow-400 bg-indigo-800 placeholder-gray-300 text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-yellow-400">

      <label class="inline-flex items-center">
        <input type="checkbox" id="agreeCheckbox" class="form-checkbox h-5 w-5 text-yellow-400 bg-indigo-700">
        <span class="ml-2 text-sm text-indigo-100">I agree to the
          <a href="https://screencraft-backend.onrender.com/terms" target="_blank" class="text-yellow-300 underline">Terms & Conditions</a>
        </span>
      </label>
    </div>

    <button onclick="submitScene()"
      class="w-full bg-yellow-400 hover:bg-yellow-500 text-indigo-900 font-semibold py-3 px-6 rounded-xl shadow-lg transition-all duration-300">Analyze Scene</button>

    <div id="output" class="mt-6 bg-indigo-800 border border-yellow-400 rounded-lg p-4 text-sm whitespace-pre-wrap shadow-md hidden text-gray-100"></div>
  </div>

  <script>
    async function submitScene() {
      const scene = document.getElementById('sceneInput').value.trim();
      const token = document.getElementById('tokenInput').value.trim();
      const agreed = document.getElementById('agreeCheckbox').checked;
      const outputDiv = document.getElementById('output');
      outputDiv.classList.remove('hidden');
      outputDiv.innerText = 'Analyzing scene...';

      if (!scene || !token || !agreed) {
        outputDiv.innerText = '⚠️ Please enter a valid scene or script, provide access token, and accept the terms.';
        return;
      }

      try {
        const response = await fetch('https://screencraft-backend.onrender.com/analyze', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token,
            'x-user-agreement': 'true'
          },
          body: JSON.stringify({ scene })
        });

        const result = await response.json();

        if (result.error) {
          outputDiv.innerText = '❌ ' + result.error;
        } else if (result.analysis) {
          outputDiv.innerHTML = `<strong class='text-yellow-300'>Analysis:</strong><br><br>${result.analysis}<br><br><em class='text-xs text-indigo-200'>${result.notice}</em>`;
        } else {
          outputDiv.innerText = 'Unexpected response.';
        }
      } catch (error) {
        outputDiv.innerText = '❌ Network or server error. Please try again.';
      }
    }
  </script>
</body>
</html>
