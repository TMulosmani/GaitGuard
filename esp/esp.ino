#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <math.h>

#define PIN_SHOULDER 26
#define PIN_ELBOW    27

const float L1 = 100.1f;
const float L2 = 114.0f;

const char* AP_SSID = "RobotArm";
const char* AP_PASS = "12345678";

WebServer server(80);
Servo shoulder;
Servo elbow;

float g_shoulder_deg = 90.0f;
float g_elbow_deg    = 90.0f;
String g_status      = "Ready.";

bool solveIK(float x, float z, float &s_out, float &e_out) {
  float r = sqrtf(x*x + z*z); //compute straight line distance from shoulder to target
  if (r > L1 + L2 - 1.0f) { g_status = "Error: out of reach"; return false; } // if r is more than length out of reach
  if (r < fabsf(L1 - L2) + 1.0f) { g_status = "Error: too close"; return false; } // if less than L1-L2 than its too close
  float c2 = (r*r - L1*L1 - L2*L2) / (2.0f * L1 * L2); // solving elbow angle r^2 = L1^2 + L2^2 - 2*L1*L2*cos(pi - theta2) rearranges to cos(theta2) = (r^2 - L1^2 - L2^2) / (2 * L1 * L2)
  c2 = constrain(c2, -1.0f, 1.0f); //handles floating point rounding errors
  float th2 = acosf(c2); //convert cos to angle in radians th2 is the angle at the elbow joint  
  float th1 = atan2f(z, x) - atan2f(L2*sinf(th2), L1 + L2*c2); //solve th1 the shoulder angle using atan2
  s_out = constrain(90.0f + th1 * RAD_TO_DEG, 0.0f, 180.0f); //convert shoulder angle to servo angle
  e_out = constrain(180.0f - th2 * RAD_TO_DEG, 0.0f, 180.0f); //convert elbow angle to servo angle
  return true;
}

void handleRoot() {
  String h = "<!DOCTYPE html><html><head><meta charset='UTF-8'>";
  h += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  h += "<title>Robot Arm</title><style>";
  h += "body{margin:0;background:#0a0c10;color:#cdd9e5;font-family:sans-serif;";
  h += "display:flex;flex-direction:column;align-items:center;padding:16px;gap:10px;}";
  h += "h1{color:#00e5ff;text-transform:uppercase;letter-spacing:.1em;margin:0;}";
  h += "p{color:#4a5568;font-size:.75rem;margin:0;text-align:center;}";
  h += "#ws{touch-action:none;cursor:crosshair;display:block;}";
  h += ".info{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;width:100%;max-width:360px;}";
  h += ".box{background:#111520;border:1px solid #1e2a3a;border-radius:6px;padding:10px;text-align:center;}";
  h += ".bl{display:block;font-size:.55rem;color:#4a5568;margin-bottom:3px;text-transform:uppercase;}";
  h += ".bv{font-size:.95rem;color:#ff6b35;}";
  h += ".status{background:#111520;border:1px solid #1e2a3a;border-radius:6px;padding:10px;font-size:.7rem;width:100%;max-width:360px;box-sizing:border-box;text-align:center;}";
  h += ".ok{color:#00ff88;border-color:#00ff88;}.err{color:#ff4455;border-color:#ff4455;}";
  h += ".btnrow{display:grid;grid-template-columns:1fr 1fr;gap:8px;width:100%;max-width:360px;}";
  h += "button{padding:10px;border:none;border-radius:6px;font-weight:700;font-size:.8rem;text-transform:uppercase;cursor:pointer;}";
  h += ".go{background:#00e5ff;color:#000;}.home{background:transparent;border:1px solid #ff6b35;color:#ff6b35;}";
  h += "</style></head><body>";
  h += "<h1>Robot Arm</h1>";
  h += "<p>Tap inside the arc to move</p>";
  h += "<canvas id='ws'></canvas>";
  h += "<div class='info'>";
  h += "<div class='box'><span class='bl'>X</span><span class='bv' id='dx'>—</span></div>";
  h += "<div class='box'><span class='bl'>Z</span><span class='bv' id='dz'>—</span></div>";
  h += "<div class='box'><span class='bl'>Reach</span><span class='bv' id='dr'>—</span></div>";
  h += "</div>";
  h += "<div class='info'>";
  h += "<div class='box'><span class='bl'>Shoulder</span><span class='bv' id='ds'>—</span></div>";
  h += "<div class='box'><span class='bl'>Elbow</span><span class='bv' id='de'>—</span></div>";
  h += "<div class='box'><span class='bl'>Status</span><span class='bv' id='dst'>—</span></div>";
  h += "</div>";
  h += "<div class='btnrow'>";
  h += "<button class='home' onclick='goHome()'>HOME</button>";
  h += "<button class='go' onclick='sendLast()'>RESEND</button>";
  h += "</div>";
  h += "<div class='status' id='st'>Tap to move</div>";

  h += "<script>";
  // simple setup - base bottom right, quarter circle up and left
  h += "const cv=document.getElementById('ws');";
  h += "const S=Math.min(window.innerWidth-32,360);";
  // canvas is SxS, base at bottom right corner
  h += "cv.width=S;cv.height=S;";
  h += "const ctx=cv.getContext('2d');";
  h += "const MAXMM=212,MINMM=14;";
  // scale so max reach = S-10 pixels
  h += "const SC=(S-10)/MAXMM;";
  h += "const MAXR=MAXMM*SC,MINR=MINMM*SC;";
  // base at bottom right
  h += "const BX=S-5,BY=S-5;";
  h += "let lx=150,lz=80;";

  h += "function draw(tx,tz){";
  h += "ctx.clearRect(0,0,S,S);";
  // draw grid first over whole canvas
  h += "ctx.strokeStyle='#1a2535';ctx.lineWidth=0.5;";
  h += "for(let i=0;i<S;i+=20){ctx.beginPath();ctx.moveTo(i,0);ctx.lineTo(i,S);ctx.stroke();}";
  h += "for(let i=0;i<S;i+=20){ctx.beginPath();ctx.moveTo(0,i);ctx.lineTo(S,i);ctx.stroke();}";
  // shade workspace arc
  h += "ctx.fillStyle='rgba(0,229,255,0.05)';";
  h += "ctx.beginPath();";
  h += "ctx.moveTo(BX,BY);";
  h += "ctx.arc(BX,BY,MAXR,Math.PI,Math.PI*0.5,true);";
  h += "ctx.closePath();";
  h += "ctx.fill();";
  // shade dead zone dark
  h += "ctx.fillStyle='rgba(0,0,0,0.4)';";
  h += "ctx.beginPath();";
  h += "ctx.moveTo(BX,BY);";
  h += "ctx.arc(BX,BY,MINR,Math.PI,Math.PI*0.5,true);";
  h += "ctx.closePath();";
  h += "ctx.fill();";
  // arc border
  h += "ctx.strokeStyle='rgba(0,229,255,0.7)';ctx.lineWidth=2;";
  h += "ctx.beginPath();ctx.arc(BX,BY,MAXR,Math.PI,Math.PI*0.5,true);ctx.stroke();";
  // dead zone border
  h += "ctx.strokeStyle='rgba(255,107,53,0.4)';ctx.lineWidth=1;ctx.setLineDash([4,4]);";
  h += "ctx.beginPath();ctx.arc(BX,BY,MINR,Math.PI,Math.PI*0.5,true);ctx.stroke();";
  h += "ctx.setLineDash([]);";
  // baseline
  h += "ctx.strokeStyle='rgba(0,229,255,0.25)';ctx.lineWidth=1;";
  h += "ctx.beginPath();ctx.moveTo(BX-MAXR,BY);ctx.lineTo(BX,BY);ctx.stroke();";
  // target dot
  h += "if(tx!==null){";
  h += "const px=BX-tx*SC,py=BY-tz*SC;";
  h += "ctx.strokeStyle='rgba(0,229,255,0.5)';ctx.lineWidth=1;ctx.setLineDash([3,3]);";
  h += "ctx.beginPath();ctx.moveTo(BX,BY);ctx.lineTo(px,py);ctx.stroke();ctx.setLineDash([]);";
  h += "ctx.fillStyle='#ff6b35';ctx.beginPath();ctx.arc(px,py,14,0,Math.PI*2);ctx.fill();";
  h += "ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(px,py,5,0,Math.PI*2);ctx.fill();}";
  // base dot
  h += "ctx.fillStyle='#00e5ff';ctx.beginPath();ctx.arc(BX,BY,8,0,Math.PI*2);ctx.fill();";
  h += "ctx.fillStyle='#0a0c10';ctx.beginPath();ctx.arc(BX,BY,3,0,Math.PI*2);ctx.fill();";
  h += "}";

  h += "function clamp(x,z){";
  h += "if(x<0)x=0;";
  h += "if(z<0)z=0;";
  h += "let r=Math.sqrt(x*x+z*z);";
  h += "if(r>MAXMM){x=x/r*MAXMM;z=z/r*MAXMM;}";
  h += "else if(r<MINMM&&r>0){x=x/r*MINMM;z=z/r*MINMM;}";
  h += "return{x:Math.round(x),z:Math.round(z)};}";

  h += "function getPos(e){";
  h += "const r=cv.getBoundingClientRect();";
  h += "const sx=S/r.width,sy=S/r.height;";
  h += "let px,py;";
  h += "if(e.changedTouches){px=(e.changedTouches[0].clientX-r.left)*sx;py=(e.changedTouches[0].clientY-r.top)*sy;}";
  h += "else{px=(e.clientX-r.left)*sx;py=(e.clientY-r.top)*sy;}";
  h += "return clamp((BX-px)/SC,(BY-py)/SC);}";

  h += "function sendMove(x,z){";
  h += "lx=x;lz=z;";
  h += "document.getElementById('dx').textContent=x+'mm';";
  h += "document.getElementById('dz').textContent=z+'mm';";
  h += "document.getElementById('dr').textContent=Math.round(Math.sqrt(x*x+z*z))+'mm';";
  h += "st('Sending...','');";
  h += "var r=new XMLHttpRequest();";
  h += "r.open('GET','/move?x='+x+'&z='+z,true);";
  h += "r.onload=function(){var t=r.responseText;";
  h += "st(t,t.startsWith('Error')?'err':'ok');";
  h += "if(!t.startsWith('Error')){draw(x,z);poll();}};";
  h += "r.onerror=function(){st('Conn error','err');};";
  h += "r.send();}";

  h += "function sendLast(){sendMove(lx,lz);}";

  h += "function goHome(){";
  h += "var r=new XMLHttpRequest();";
  h += "r.open('GET','/home',true);";
  h += "r.onload=function(){st(r.responseText,'ok');draw(null,null);poll();};";
  h += "r.send();}";

  h += "function poll(){";
  h += "var r=new XMLHttpRequest();";
  h += "r.open('GET','/state',true);";
  h += "r.onload=function(){try{var j=JSON.parse(r.responseText);";
  h += "document.getElementById('ds').textContent=j.s.toFixed(1)+'deg';";
  h += "document.getElementById('de').textContent=j.e.toFixed(1)+'deg';}catch(e){}};";
  h += "r.send();}";

  h += "function st(m,c){var e=document.getElementById('st');e.textContent=m;e.className='status '+c;}";

  h += "cv.addEventListener('touchend',function(e){e.preventDefault();var p=getPos(e);sendMove(p.x,p.z);},false);";
  h += "cv.addEventListener('click',function(e){var p=getPos(e);sendMove(p.x,p.z);});";

  h += "draw(null,null);poll();setInterval(poll,3000);";
  h += "</script></body></html>";
  server.send(200, "text/html", h);
}

void handleMove() {
  if (!server.hasArg("x") || !server.hasArg("z")) {
    server.send(400, "text/plain", "Error: missing x or z");
    return;
  }
  float x = server.arg("x").toFloat();
  float z = server.arg("z").toFloat();
  float s, e;
  if (!solveIK(x, z, s, e)) {
    server.send(200, "text/plain", g_status);
    return;
  }
  shoulder.write((int)s);
  elbow.write((int)e);
  g_shoulder_deg = s;
  g_elbow_deg    = e;
  g_status = "OK S:" + String((int)s) + " E:" + String((int)e);
  Serial.println("X:" + String(x,1) + " Z:" + String(z,1) +
                 " -> S:" + String((int)s) + " E:" + String((int)e));
  server.send(200, "text/plain", g_status);
}

void handleHome() {
  shoulder.write(90);
  elbow.write(90);
  g_shoulder_deg = 90;
  g_elbow_deg    = 90;
  g_status = "Homed";
  Serial.println("Homed");
  server.send(200, "text/plain", g_status);
}

void handleState() {
  String j = "{\"s\":" + String(g_shoulder_deg,1) + ",\"e\":" + String(g_elbow_deg,1) + "}";
  server.send(200, "application/json", j);
}

void setup() {
  Serial.begin(115200);
  delay(500);
  shoulder.attach(PIN_SHOULDER, 500, 2400);
  elbow.attach(PIN_ELBOW, 500, 2400);
  shoulder.write(90);
  elbow.write(90);
  Serial.println("Servos ready");
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASS);
  delay(500);
  Serial.println("AP: " + WiFi.softAPIP().toString());
  server.on("/",      handleRoot);
  server.on("/move",  handleMove);
  server.on("/home",  handleHome);
  server.on("/state", handleState);
  server.on("/test",  [](){
    int s=server.arg("s").toInt();
    int e=server.arg("e").toInt();
    shoulder.write(s);
    elbow.write(e);
    Serial.println("TEST S:"+String(s)+" E:"+String(e));
    server.send(200,"text/plain","S:"+String(s)+" E:"+String(e));
  });
  server.begin();
  Serial.println("Ready. Connect to RobotArm -> 192.168.4.1");
}

void loop() {
  server.handleClient();
}
