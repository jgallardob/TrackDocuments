// Funciones de control UI
function showToast(msg, isError=false) {
    const t = document.getElementById("toast");
    const m = document.getElementById("toastMessage");
    t.style.border = isError ? "1px solid var(--danger-color)" : "1px solid var(--glass-border)";
    m.innerHTML = msg;
    t.style.display = "block";
    setTimeout(() => { t.style.display="none"; }, 6000);
}

function setLoggedIn(userId) {
    document.getElementById('sessionStatus').classList.add('active');
    document.getElementById('sessionStatus').title = "Conectado: " + userId;
    document.getElementById('logoutBtn').style.display = 'block';
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('loggedInView').style.display = 'block';
    document.getElementById('vault-content').style.display = 'block';
    document.getElementById('vault-locked').style.display = 'none';
    loadRegistry();
}

function setLoggedOut() {
    document.getElementById('sessionStatus').classList.remove('active');
    document.getElementById('sessionStatus').title = "Desconectado";
    document.getElementById('loggedInView').style.display = 'none';
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('vault-content').style.display = 'none';
    document.getElementById('vault-locked').style.display = 'block';
}

// Iconos SVG Reutilizables
const SVG_FILE = `<svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16" style="vertical-align: middle; margin-right: 4px;"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>`;
const SVG_DOWN = `<svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14" style="vertical-align: middle; margin-right: 4px;"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>`;

// Cargar Registro de archivos
async function loadRegistry() {
    const registryDiv = document.getElementById("fileRegistry");
    registryDiv.innerHTML = '<span style="color: var(--text-muted); font-size: 0.85rem; padding: 0.5rem; display: block;">Cargando registro...</span>';
    try {
        const res = await fetch("/files");
        if (res.ok) {
            const data = await res.json();
            if (data.files && data.files.length > 0) {
                registryDiv.innerHTML = "";
                data.files.forEach(f => {
                    const docName = f.name;
                    const p = document.createElement("div");
                    p.style.cssText = "font-size: 0.9rem; padding: 0.4rem; border-bottom: 1px solid rgba(255,255,255,0.05); color: var(--text-light);";
                    p.innerHTML = `${SVG_FILE} ${docName}`;
                    registryDiv.appendChild(p);
                });
                
                // Árbol de Auditoría
                if (data.audit_tree) {
                    const treeDiv = document.getElementById("auditTree");
                    if (data.audit_tree.length > 0) {
                        let html = '<ul style="list-style-type:none; padding-left:0; margin:0;">';
                        data.audit_tree.forEach(t => {
                            html += `<li style="margin-bottom: 12px; padding-left: 10px; border-left: 2px solid var(--primary-color);">`;
                            html += `<strong style="color:var(--text-light); word-break: break-all; display: flex; align-items: center;">${SVG_FILE} ${t.name}</strong>`;
                            if (t.downloads && t.downloads.length > 0) {
                                html += `<ul style="list-style-type:none; padding-left:15px; margin-top:6px;">`;
                                t.downloads.forEach(d => {
                                    html += `<li style="margin-bottom: 4px; font-size: 0.75rem; display: flex; align-items: center;">${SVG_DOWN} <span style="color:#10b981; margin-right: 4px;">Extraído:</span> ${d}</li>`;
                                });
                                html += `</ul>`;
                            } else {
                                html += `<p style="margin: 5px 0 0 15px; font-size: 0.75rem; color: #64748b;">Aún no ha sido extraído.</p>`;
                            }
                            html += `</li>`;
                        });
                        html += '</ul>';
                        treeDiv.innerHTML = html;
                    } else {
                        treeDiv.innerHTML = '<p>No hay archivos subidos por ti.</p>';
                    }
                }
            } else {
                registryDiv.innerHTML = '<span style="color: var(--text-muted); font-size: 0.85rem; padding: 0.5rem; display: block;">La bóveda está vacía.</span>';
            }
        }
    } catch(e) {
        registryDiv.innerHTML = '<span style="color: var(--danger-color); font-size: 0.85rem; padding: 0.5rem; display: block;">Error leyendo la bóveda.</span>';
    }
}

// Check session on load
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch("/me");
        if (res.ok) {
            const data = await res.json();
            setLoggedIn(data.user_id);
        }
    } catch (e) {}
});

async function logout() {
    const res = await fetch("/logout", { method: "POST" });
    if (res.ok) {
        setLoggedOut();
        showToast("Sesión Terminada");
    }
}

document.getElementById('fileInput').addEventListener('change', function(e) {
    const fileName = e.target.files[0] ? e.target.files[0].name : 'Seleccionar documento PDF...';
    document.getElementById('fileNameDisplay').textContent = fileName;
});

document.getElementById("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const u = document.getElementById("username").value;
    const p = document.getElementById("password").value;
    const body = new URLSearchParams({ username: u, password: p });
    
    const res = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body
    });
    
    if(res.ok) {
        const data = await res.json();
        setLoggedIn(data.user_id);
        showToast(`Bienvenido <b>${data.user_id}</b>`);
    } else {
        showToast("Error: Autenticación fallida", true);
    }
});

async function uploadFile() {
    const input = document.getElementById("fileInput");
    if (!input.files[0]) return showToast("Selecciona un archivo", true);
    
    const formData = new FormData();
    formData.append("file", input.files[0]);

    const res = await fetch("/upload", {
        method: "POST",
        body: formData
    });
    
    if(res.ok) {
        showToast("Archivo ingresado al Vault");
        input.value = "";
        document.getElementById('fileNameDisplay').textContent = "Seleccionar documento PDF...";
        loadRegistry();
    } else {
        showToast("Error en la subida", true);
    }
}
