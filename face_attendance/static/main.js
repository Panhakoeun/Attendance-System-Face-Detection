 document.getElementById("registerForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("regName").value.trim();
      const imgInput = document.getElementById("regImage");
      if (!name || imgInput.files.length === 0) return alert("Name and image required.");

      const fd = new FormData();
      fd.append("name", name);
      fd.append("image", imgInput.files[0]);

      const res = await fetch("/api/register", { method: "POST", body: fd });
      const j = await res.json();
      alert(j.message || j.error);
    });

    // --- Webcam scan ---
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    let streamRef = null;
    let autoScanTimer = null;
    let scanInFlight = false;
    let unknownPrompted = false;
    const autoScanIntervalMs = 2000;

    async function scanOnce() {
      if (!video || !canvas) return;
      // Ensure canvas matches current video dimensions
      const ctx = canvas.getContext("2d");
      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth || canvas.width;
        canvas.height = video.videoHeight || canvas.height;
      }
      // Draw current frame
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      // Prepare downscaled offscreen canvas
      const tw = 480;
      const ratio = canvas.width / canvas.height;
      const dw = Math.min(canvas.width, tw);
      const dh = Math.round(dw / ratio);
      const off = document.createElement('canvas');
      off.width = dw; off.height = dh;
      const octx = off.getContext('2d');
      octx.drawImage(canvas, 0, 0, dw, dh);
      // Get JPEG blob
      const { blob } = await new Promise(resolve => {
        off.toBlob(b => resolve({ blob: b }), "image/jpeg", 0.7);
      });
      const fd = new FormData();
      fd.append("image", blob, "capture.jpg");
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), 7000);
      let j = {};
      try {
        const res = await fetch("/api/recognize", { method: "POST", body: fd, signal: controller.signal });
        j = await res.json();
      } catch (_) {
        j = { success: false, message: "Recognition request timed out." };
      } finally {
        clearTimeout(t);
      }
      document.getElementById("recResult").innerText = j.message || j.error || "";
      // Draw detections on full-size canvas
      if (j && Array.isArray(j.detections)) {
        canvas.classList.remove("hidden");
        const ctx2 = canvas.getContext("2d");
        ctx2.strokeStyle = "#00FF00";
        ctx2.lineWidth = 2;
        ctx2.fillStyle = "#00FF00";
        ctx2.font = "bold 22px sans-serif";
        const sx = canvas.width / (dw || canvas.width);
        const sy = canvas.height / (dh || canvas.height);
        j.detections.forEach(d => {
          const left = Math.round((d.left | 0) * sx);
          const top = Math.round((d.top | 0) * sy);
          const right = Math.round((d.right | 0) * sx);
          const bottom = Math.round((d.bottom | 0) * sy);
          const w = right - left;
          const h = bottom - top;
          ctx2.strokeRect(left, top, w, h);
          const label = d.name && d.name.length ? d.name : "Unknown";
          const textY = Math.max(12, top - 4);
          ctx2.fillText(label, left + 2, textY);
        });

        const hasUnknown = j.detections.some(d => !d.name || d.name === "Unknown");
        if (hasUnknown && !unknownPrompted) {
          unknownPrompted = true;
          const proposed = prompt("Face not recognized. Enter name to register this face (or Cancel):", "");
          if (proposed && proposed.trim().length > 0) {
            try {
              const regFd = new FormData();
              regFd.append("name", proposed.trim());
              regFd.append("image", blob, "register.jpg");
              const regRes = await fetch("/api/register", { method: "POST", body: regFd });
              const regJ = await regRes.json();
              alert(regJ.message || regJ.error || "");
            } catch (_) {}
          }
          setTimeout(() => { unknownPrompted = false; }, 3000);
        }
      }
    }

    function startAutoScan() {
      if (autoScanTimer) return;
      autoScanTimer = setInterval(async () => {
        if (scanInFlight) return;
        scanInFlight = true;
        try { await scanOnce(); } catch (_) {} finally { scanInFlight = false; }
      }, autoScanIntervalMs);
    }

    function stopAutoScan() {
      if (autoScanTimer) {
        clearInterval(autoScanTimer);
        autoScanTimer = null;
      }
      scanInFlight = false;
      unknownPrompted = false;
    }

    document.getElementById("scanBtn").addEventListener("click", async () => {
      document.getElementById("webcamArea").classList.remove("hidden");
      // Make canvas visible so annotated frame can be seen after capture
      canvas.classList.remove("hidden");
      streamRef = await navigator.mediaDevices.getUserMedia({ 
        video: { width: { ideal: 640 }, height: { ideal: 480 } }
      });
      video.srcObject = streamRef;
      await new Promise(res => video.onloadedmetadata = res);
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      video.style.width = '100%';
      video.style.height = 'auto';
      canvas.style.width = '100%';
      canvas.style.height = 'auto';
      // Start auto scan
      startAutoScan();
    });

    document.getElementById("closeCamBtn").addEventListener("click", () => {
      if (streamRef) streamRef.getTracks().forEach(t => t.stop());
      document.getElementById("webcamArea").classList.add("hidden");
      stopAutoScan();
    });

    document.getElementById("captureBtn").addEventListener("click", async () => {
      // Manual one-off scan
      if (scanInFlight) return;
      scanInFlight = true;
      try { await scanOnce(); } finally { scanInFlight = false; }
    });

    // --- Load attendance info and render clickable names ---
    const userNamesDiv = document.getElementById("userNames");
    const userAttendanceDiv = document.getElementById("userAttendance");
    const userTitle = document.getElementById("userTitle");

    async function loadUsers() {
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), 7000);
      let j = {};
      try {
        const res = await fetch("/api/users", { signal: controller.signal });
        j = await res.json();
      } catch (_) {
        return [];
      } finally {
        clearTimeout(t);
      }
      if (!j.success) {
        alert("Error loading users");
        return [];
      }
      const names = Array.isArray(j.users) ? j.users : [];
      return names;
    }

    function renderNames(names) {
      if (names.length === 0) {
        userNamesDiv.innerHTML = '<p class="text-sm text-gray-600">No names found yet.</p>';
        return;
      }
      userNamesDiv.innerHTML = '';
      names.forEach(name => {
        const btn = document.createElement('button');
        btn.textContent = name;
        btn.className = 'text-left px-3 py-2 rounded border hover:bg-gray-50';
        btn.addEventListener('click', async () => {
          await showUserAttendance(name);
        });
        userNamesDiv.appendChild(btn);
      });
    }

    function renderUserTable(name, records) {
      if (!records || records.length === 0) {
        userAttendanceDiv.innerHTML = '<p class="text-sm text-gray-600">No attendance for this user.</p>';
        return;
      }
      let html = `<table class="min-w-full border"><thead><tr>` +
                 `<th class="border px-2 py-1">ID</th>` +
                 `<th class="border px-2 py-1">Date</th>` +
                 `<th class="border px-2 py-1">Time</th>` +
                 `</tr></thead><tbody>`;
      records.forEach(r => {
        html += `<tr>` +
                `<td class="border px-2 py-1">${r.id || ''}</td>` +
                `<td class="border px-2 py-1">${r.date || ''}</td>` +
                `<td class="border px-2 py-1">${r.time || ''}</td>` +
                `</tr>`;
      });
      html += `</tbody></table>`;
      userAttendanceDiv.innerHTML = html;
    }

    async function showUserAttendance(name) {
      userTitle.textContent = `Attendance for ${name}`;
      userAttendanceDiv.innerHTML = '<p class="text-sm text-gray-600">Loading...</p>';
      const res = await fetch(`/api/attendance/${encodeURIComponent(name)}`);
      const j = await res.json();
      const records = j && j.success && Array.isArray(j.attendance) ? j.attendance : [];
      renderUserTable(name, records);
    }

    document.getElementById("loadBtn").addEventListener("click", async () => {
      const names = await loadUsers();
      renderNames(names);
      userTitle.textContent = 'Select a name to view attendance';
      userAttendanceDiv.innerHTML = '';
    });