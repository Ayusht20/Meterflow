const API = "https://meterflow-5qrc.onrender.com";

window.onload = function () {

    if (document.getElementById("api_list")) {
        loadAPIs();
    }

    if (document.getElementById("usage_table")) {
        loadUsage();
    }

    if (document.getElementById("dashboard_data")) {
        loadDashboard();
    }
};

// ---------------- SIGNUP ----------------
async function signup() {
    let form = new FormData();
    form.append("email", document.getElementById("s_email").value);
    form.append("password", document.getElementById("s_pass").value);

    let res = await fetch(API + "/signup", {
        method: "POST",
        body: form
    });

    let data = await res.json();
    document.getElementById("msg").innerText = data.message || data.detail;
}

// ---------------- LOGIN ----------------
async function login() {
    let form = new FormData();
    form.append("email", document.getElementById("l_email").value);
    form.append("password", document.getElementById("l_pass").value);

    let res = await fetch(API + "/login", {
        method: "POST",
        body: form
    });

    let data = await res.json();

    if (data.access_token) {
        localStorage.setItem("token", data.access_token);
        window.location.href = "/dashboard.html";
    } else {
        document.getElementById("msg").innerText = data.detail;
    }
}

// ---------------- LOAD APIs ----------------
async function loadAPIs() {

    let res = await fetch(API + "/apis");
    let data = await res.json();

    let select = document.getElementById("api_list");
    if (!select) return;

    select.innerHTML = "";

    data.apis.forEach(api => {
        let option = document.createElement("option");
        option.value = api[0];
        option.text = api[1];
        select.appendChild(option);
    });
}

// ---------------- GENERATE KEY ----------------
async function generateKey() {

    let token = localStorage.getItem("token");

    if (!token) {
        window.location.href = "/";
        return;
    }

    let api_id = document.getElementById("api_list").value;

    let form = new FormData();
    form.append("api_id", api_id);

    let res = await fetch(API + "/generate-key", {
        method: "POST",
        headers: {
            "Authorization": "Bearer " + token
        },
        body: form
    });

    let data = await res.json();

    document.getElementById("api_key_output").innerText =
        "API Key: " + data.api_key;
}

// ---------------- LOAD USAGE ----------------
async function loadUsage() {

    let token = localStorage.getItem("token");
    if (!token) return;

    let res = await fetch(API + "/my-usage", {
        headers: {
            "Authorization": "Bearer " + token
        }
    });

    let data = await res.json();

    let table = document.getElementById("usage_table");
    if (!table) return;

    table.innerHTML = "";

    data.usage.forEach(row => {
        let tr = document.createElement("tr");
        tr.innerHTML = `
        <td>${row[0]}</td>
        <td>${row[1]}</td>
    `;

        table.appendChild(tr);
    });
}

// ---------------- LOAD DASHBOARD ----------------
async function loadDashboard() {

    let token = localStorage.getItem("token");

    if (!token) {
        window.location.href = "/";
        return;
    }

    let div = document.getElementById("dashboard_data");
    if (div) div.innerHTML = "Loading...";

    let res = await fetch(API + "/my-dashboard", {
        headers: {
            "Authorization": "Bearer " + token
        }
    });

    let data = await res.json();

    // 🔥 NEW FEATURES (SAFE ADDITIONS)
    updateStats(data);

    if (data.data.length === 0) {
        document.getElementById("empty_state").style.display = "block";
        document.getElementById("analytics_content").style.display = "none";
    } else {
        document.getElementById("empty_state").style.display = "none";
        document.getElementById("analytics_content").style.display = "block";
    
        renderPieChart(data);
        loadAnalytics();
    }  // real analytics

    if (!div) return;

    div.innerHTML = "";

    data.data.forEach(item => {

        let slug = item.api_name.toLowerCase().split(" ")[0];

        let html = `
        <div class="card">
            <h3>${item.api_name}</h3>

            <p><b>API Key:</b></p>
            <code>${item.api_key}</code>

            <p>Usage: ${item.usage}</p>
            <p>Credits: ${item.balance}</p>

            <p><b>Endpoint:</b></p>
            <code>
        ${API}/gateway/${slug}/${slug}?api_key=YOUR_API_KEY
            </code>

            <p style="color:gray;">
            Replace YOUR_API_KEY with your key
            </p>

            <button onclick="copyKey('${item.api_key}')">Copy Key</button>
            <button onclick="copyEndpoint('${slug}')">Copy Endpoint</button>


        </div>
        `;

        div.innerHTML += html;
    });
}

// ---------------- REAL ANALYTICS ----------------
async function loadAnalytics() {

    let token = localStorage.getItem("token");
    if (!token) return;

    let res = await fetch(API + "/analytics", {
        headers: {
            "Authorization": "Bearer " + token
        }
    });

    let data = await res.json();

    renderLineChart(data.data);
}
let lineChartInstance = null;

function renderLineChart(rows) {

    let ctx = document.getElementById("lineChart");
    if (!ctx) return;

    // 🎯 Fill missing dates (last 7 days)
    let map = {};
    rows.forEach(r => map[r[0]] = r[1]);

    let labels = [];
    let values = [];

    for (let i = 6; i >= 0; i--) {
        let d = new Date();
        d.setDate(d.getDate() - i);

        let date = d.toISOString().split("T")[0];

        labels.push(date);
        values.push(map[date] || 0);
    }

    // 🔥 Destroy old chart
    if (lineChartInstance) {
        lineChartInstance.destroy();
    }

    // 🎨 Gradient (premium feel)
    let gradient = ctx.getContext("2d").createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, "rgba(99,102,241,0.6)");
    gradient.addColorStop(1, "rgba(99,102,241,0)");

    lineChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: "API Requests",
                data: values,
                borderColor: "#6366f1",
                backgroundColor: gradient,
                borderWidth: 3,
                tension: 0.45,
                fill: true,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            animation: {
                duration: 1200,
                easing: "easeOutQuart"
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: "#111",
                    titleColor: "#fff",
                    bodyColor: "#ddd",
                    borderColor: "#333",
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    ticks: { color: "#aaa" },
                    grid: { color: "rgba(255,255,255,0.05)" }
                },
                y: {
                    ticks: { color: "#aaa" },
                    grid: { color: "rgba(255,255,255,0.05)" }
                }
            }
        }
    });
}

// ---------------- PIE CHART ----------------
let pieChartInstance = null;

function renderPieChart(data) {

    let ctx = document.getElementById("pieChart");
    if (!ctx) return;

    let labels = data.data.map(d => d.api_name);
    let values = data.data.map(d => d.usage);

    if (pieChartInstance) {
        pieChartInstance.destroy();
    }

    pieChartInstance = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: [
                    "#6366f1",
                    "#22c55e",
                    "#f59e0b",
                    "#ef4444",
                    "#06b6d4"
                ],
                borderWidth: 0
            }]
        },
        options: {
            cutout: "75%",
            animation: {
                animateRotate: true,
                duration: 1200
            },
            plugins: {
                legend: {
                    labels: {
                        color: "#ccc"
                    }
                }
            }
        }
    });
}

// ---------------- STATS ----------------
function animateValue(id, start, end, duration = 800) {
    let obj = document.getElementById(id);
    if (!obj) return;

    let startTime = null;

    function step(timestamp) {
        if (!startTime) startTime = timestamp;

        let progress = Math.min((timestamp - startTime) / duration, 1);
        let value = Math.floor(progress * (end - start) + start);

        obj.innerText = value;

        if (progress < 1) {
            requestAnimationFrame(step);
        }
    }

    requestAnimationFrame(step);
}

function updateStats(data) {

    let totalRequests = 0;
    let totalCredits = 0;

    data.data.forEach(item => {
        totalRequests += item.usage;
        totalCredits += item.balance;
    });

    animateValue("total_requests", 0, totalRequests);
    animateValue("total_apis", 0, data.data.length);
    animateValue("total_credits", 0, totalCredits);
}

// ---------------- COPY ----------------
function copyKey(key) {
    navigator.clipboard.writeText(key);
    showToast("API Key copied!");
}

function copyEndpoint(slug) {
    let text = `${API}/gateway/${slug}/${slug}?api_key=YOUR_API_KEY`;
    navigator.clipboard.writeText(text);
    showToast("Endpoint copied!");
}

// ---------------- TOAST ----------------
function showToast(msg) {
    let t = document.createElement("div");
    t.innerText = msg;
    t.style.position = "fixed";
    t.style.bottom = "20px";
    t.style.right = "20px";
    t.style.background = "black";
    t.style.color = "white";
    t.style.padding = "10px";
    t.style.borderRadius = "5px";

    document.body.appendChild(t);

    setTimeout(() => t.remove(), 2000);
}

// ---------------- RECHARGE ----------------
function rechargePrompt(api_key = null) {

    let key = api_key || document.getElementById("re_api_key").value;
    let amount = document.getElementById("amount").value;

    if (!key || !amount) {
        alert("Enter API key and amount");
        return;
    }

    if (isNaN(amount)) {
        alert("Amount must be number");
        return;
    }

    recharge(key, parseFloat(amount));
}
async function loadPayments() {

    let token = localStorage.getItem("token");

    let res = await fetch(API + "/payments", {
        headers: {
            "Authorization": "Bearer " + token
        }
    });

    let data = await res.json();

    let table = document.getElementById("payments_table");
    let empty = document.getElementById("payments_empty");

    if (!table) return;

    table.innerHTML = "";

    if (!data.payments || data.payments.length === 0) {
        empty.style.display = "block";
        return;
    } else {
        empty.style.display = "none";
    }

    data.payments.forEach(p => {

        let tr = document.createElement("tr");

        tr.innerHTML = `
            <td class="amount">₹${p[0]}</td>
            <td>${p[1]}</td>
            <td><code>${p[2]}</code></td>
           
            <td>${new Date(p[3]).toLocaleString()}</td>
        `;

        table.appendChild(tr);
    });
}
async function recharge(api_key, amount) {

    let form = new FormData();
    form.append("amount", amount);
    form.append("api_key",api_key)
    let res = await fetch(API + "/create-order", {
        method: "POST",
        headers: {
            "Authorization": "Bearer " + localStorage.getItem("token")
        },
        body: form
    });

    let data = await res.json();

    let options = {
        key: data.key,
        amount: amount * 100,
        currency: "INR",
        order_id: data.order_id,

        handler: async function (response) {

            let verifyForm = new FormData();
            verifyForm.append("razorpay_order_id", response.razorpay_order_id);
            verifyForm.append("razorpay_payment_id", response.razorpay_payment_id);
            verifyForm.append("razorpay_signature", response.razorpay_signature);
            verifyForm.append("api_key", api_key);
            verifyForm.append("amount", amount);

            let verifyRes = await fetch(API + "/verify-payment", {
                method: "POST",
                body: verifyForm
            });

            let verifyData = await verifyRes.json();

            alert(verifyData.message);
            loadDashboard();
        }
    };

    let rzp = new Razorpay(options);
    rzp.open();
}

let isLogin = true;

function showLogin() {
    isLogin = true;
    authTitle.innerText = "Login";
    authBtn.innerText = "Login";

    l_email.style.display = "block";
    l_pass.style.display = "block";

    s_email.style.display = "none";
    s_pass.style.display = "none";
}

function showSignup() {
    isLogin = false;
    authTitle.innerText = "Signup";
    authBtn.innerText = "Signup";

    l_email.style.display = "none";
    l_pass.style.display = "none";

    s_email.style.display = "block";
    s_pass.style.display = "block";
}

function handleAuth() {
    if (isLogin) login();
    else signup();
}

function logout() {
    localStorage.removeItem("token");
    window.location.href = "/index.html";
}
function showSection(id, el) {
    document.querySelectorAll(".section").forEach(s => s.style.display = "none");
    document.getElementById(id).style.display = "block";

    document.querySelectorAll(".sidebar p").forEach(p => p.classList.remove("active"));
    if (el) el.classList.add("active");
}