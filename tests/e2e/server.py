# -*- coding: utf-8 -*-
"""
E2E stub server for JALIY.
- Mimics Vercel rewrites: /, /analysis, /comparison, /analyze, /compare -> index.html
- Stubs /api/analyze and /api/compare with schema-valid, evidence-grounded JSON
  (quotes are literal substrings of the test contracts, so the frontend's
  anti-hallucination gate accepts them).
- Counts POST hits per endpoint (GET /__counts) so tests can assert that
  double-clicks never produce duplicate requests.
"""
import json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = (ROOT / "index.html").read_bytes()

CONTRACT_A = (
    "المادة الأولى: يلتزم العميل بسداد رسوم اشتراك شهرية قدرها ٥٠٠ ريال سعودي في بداية كل شهر ميلادي. "
    "المادة الثانية: في حال إنهاء العقد قبل انتهاء مدته يتحمل العميل غرامة إنهاء مبكر قدرها ١٠٠٠ ريال سعودي. "
    "المادة الثالثة: يحق للعميل الحصول على نسخة موقعة من العقد في أي وقت. "
    "المادة الرابعة: يتجدد هذا العقد تلقائيًا لمدة سنة إضافية ما لم يخطر أحد الطرفين الآخر كتابيًا قبل ثلاثين يومًا من نهاية المدة."
)
CONTRACT_B = (
    "البند الأول: رسوم الاشتراك الشهرية ثلاثمائة ريال سعودي تدفع في بداية كل شهر. "
    "البند الثاني: يجوز للعميل إنهاء العقد في أي وقت دون أي غرامة مالية. "
    "البند الثالث: مدة هذا العقد سنة واحدة غير قابلة للتجديد التلقائي. "
    "البند الرابع: تخضع جميع النزاعات الناشئة عن هذا العقد لأنظمة المملكة العربية السعودية."
)

ANALYSIS = {
    "document": {"contractType": "اشتراك", "typeConfidence": 0.9, "typeReason": "رسوم اشتراك شهرية",
                 "language": "ar", "parties": ["العميل", "مقدم الخدمة"], "duration": "سنة"},
    "summary": {"overview": "عقد اشتراك شهري برسوم ٥٠٠ ريال، يتضمن غرامة إنهاء مبكر قدرها ١٠٠٠ ريال وتجديدًا تلقائيًا سنويًا.",
                "purpose": "تنظيم خدمة اشتراك مدفوعة",
                "importantPoints": ["غرامة إنهاء مبكر ١٠٠٠ ريال", "تجديد تلقائي لمدة سنة", "مهلة إخطار ٣٠ يومًا لعدم التجديد"]},
    "risks": [
        {"title": "غرامة إنهاء مبكر", "level": "high", "category": "رسوم",
         "explanation": "إنهاء العقد قبل نهاية مدته يكلّف ١٠٠٠ ريال.",
         "whyItMatters": "قد تدفع مبلغًا كبيرًا إذا غيّرت رأيك.", "possibleImpact": "خسارة ١٠٠٠ ريال",
         "recommendedAction": "تأكد من مدة الالتزام قبل التوقيع.", "amount": "١٠٠٠ ريال", "deadline": None,
         "pageNumber": 1, "sourceText": "يتحمل العميل غرامة إنهاء مبكر قدرها ١٠٠٠ ريال سعودي", "confidence": 0.95},
        {"title": "تجديد تلقائي", "level": "medium", "category": "تجديد",
         "explanation": "العقد يتجدد تلقائيًا سنة إضافية ما لم تخطر الطرف الآخر.",
         "whyItMatters": "قد تُلزم بسنة جديدة دون قصد.", "possibleImpact": "التزام مالي لسنة إضافية",
         "recommendedAction": "سجّل موعد الإخطار قبل ٣٠ يومًا.", "amount": None, "deadline": "٣٠ يومًا قبل نهاية المدة",
         "pageNumber": 1, "sourceText": "يتجدد هذا العقد تلقائيًا لمدة سنة إضافية", "confidence": 0.9},
    ],
    "rights": [
        {"title": "الحصول على نسخة من العقد", "explanation": "يمكنك طلب نسخة موقعة في أي وقت.",
         "beneficiary": "العميل", "conditions": "", "pageNumber": 1,
         "sourceText": "يحق للعميل الحصول على نسخة موقعة من العقد في أي وقت", "confidence": 0.9},
    ],
    "obligations": [
        {"title": "سداد رسوم الاشتراك", "responsibleParty": "العميل",
         "requiredAction": "سداد ٥٠٠ ريال في بداية كل شهر", "deadline": "بداية كل شهر",
         "consequenceOfFailure": "", "pageNumber": 1,
         "sourceText": "يلتزم العميل بسداد رسوم اشتراك شهرية قدرها ٥٠٠ ريال سعودي", "confidence": 0.9},
    ],
    "financialDetails": [
        {"label": "رسوم الاشتراك الشهرية", "amount": "٥٠٠", "currency": "ريال سعودي", "frequency": "شهري",
         "refundable": "غير محدد", "conditions": "", "pageNumber": 1,
         "sourceText": "رسوم اشتراك شهرية قدرها ٥٠٠ ريال سعودي", "confidence": 0.9},
    ],
    "deadlines": [
        {"title": "مهلة الإخطار بعدم التجديد", "dateOrDuration": "٣٠ يومًا قبل نهاية المدة", "kind": "مدة",
         "importance": "لتفادي التجديد التلقائي", "pageNumber": 1,
         "sourceText": "ما لم يخطر أحد الطرفين الآخر كتابيًا قبل ثلاثين يومًا", "confidence": 0.85},
    ],
    "unclearItems": [],
    "overallRisk": {"level": "medium", "explanation": "غرامة إنهاء مبكر وتجديد تلقائي يتطلبان انتباهًا قبل التوقيع."},
}

COMPARISON = {
    "meta": {"contractAType": "اشتراك", "contractBType": "اشتراك"},
    "verdict": {"summary": "العقد الثاني أخف كلفة وأكثر مرونة: رسوم أقل، لا غرامة إنهاء، ولا تجديد تلقائي.",
                "moreFavorable": {"party": "العميل", "contract": "B", "reason": "لا غرامة إنهاء ولا تجديد تلقائي ورسوم أقل."}},
    "riskComparison": {
        "contractA": {"level": "medium", "explanation": "غرامة إنهاء مبكر وتجديد تلقائي."},
        "contractB": {"level": "low", "explanation": "إنهاء دون غرامة ومدة محددة."},
        "summary": "العقد الأول أعلى مخاطرة على العميل من الثاني."},
    "differences": [
        {"aspect": "fees", "title": "قيمة رسوم الاشتراك",
         "contractA": "٥٠٠ ريال شهريًا", "contractB": "ثلاثمائة ريال شهريًا",
         "impact": "فارق ٢٠٠ ريال شهريًا لصالح العقد الثاني.", "advantage": "B",
         "evidence": [
             {"contract": "A", "pageNumber": 1, "quote": "رسوم اشتراك شهرية قدرها ٥٠٠ ريال سعودي"},
             {"contract": "B", "pageNumber": 1, "quote": "رسوم الاشتراك الشهرية ثلاثمائة ريال سعودي"}],
         "confidence": 0.95},
        {"aspect": "termination", "title": "غرامة الإنهاء المبكر",
         "contractA": "غرامة ١٠٠٠ ريال عند الإنهاء قبل انتهاء المدة", "contractB": "إنهاء في أي وقت دون غرامة",
         "impact": "العقد الثاني يمنح حرية خروج كاملة.", "advantage": "B",
         "evidence": [
             {"contract": "A", "pageNumber": 1, "quote": "يتحمل العميل غرامة إنهاء مبكر قدرها ١٠٠٠ ريال سعودي"},
             {"contract": "B", "pageNumber": 1, "quote": "يجوز للعميل إنهاء العقد في أي وقت دون أي غرامة مالية"}],
         "confidence": 0.95},
        {"aspect": "renewal", "title": "التجديد التلقائي",
         "contractA": "يتجدد تلقائيًا لمدة سنة إضافية", "contractB": "غير قابل للتجديد التلقائي",
         "impact": "العقد الأول قد يلزمك بسنة إضافية دون قصد.", "advantage": "B",
         "evidence": [
             {"contract": "A", "pageNumber": 1, "quote": "يتجدد هذا العقد تلقائيًا لمدة سنة إضافية"},
             {"contract": "B", "pageNumber": 1, "quote": "غير قابلة للتجديد التلقائي"}],
         "confidence": 0.9},
    ],
    "similarities": [
        {"title": "موعد سداد الرسوم", "explanation": "كلا العقدين يستحق الرسوم في بداية كل شهر.",
         "evidence": [
             {"contract": "A", "pageNumber": 1, "quote": "في بداية كل شهر ميلادي"},
             {"contract": "B", "pageNumber": 1, "quote": "تدفع في بداية كل شهر"}],
         "confidence": 0.9},
    ],
    "onlyInA": [
        {"title": "حق الحصول على نسخة من العقد", "explanation": "العقد الثاني لا ينص على هذا الحق.",
         "pageNumber": 1, "quote": "يحق للعميل الحصول على نسخة موقعة من العقد في أي وقت", "confidence": 0.9},
    ],
    "onlyInB": [
        {"title": "القانون الواجب التطبيق", "explanation": "العقد الأول لا يحدد جهة الاختصاص عند النزاع.",
         "pageNumber": 1, "quote": "تخضع جميع النزاعات الناشئة عن هذا العقد لأنظمة المملكة العربية السعودية", "confidence": 0.9},
    ],
    "reviewPoints": [
        {"title": "مهلة الإخطار في العقد الأول", "why": "٣٠ يومًا قبل نهاية المدة لتجنب التجديد التلقائي."},
    ],
}

COUNTS = {"analyze": 0, "compare": 0}
LOCK = threading.Lock()

def anthropic_wrap(obj):
    return json.dumps({
        "content": [{"type": "text", "text": json.dumps(obj, ensure_ascii=False)}],
        "stop_reason": "end_turn",
    }, ensure_ascii=False).encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep test output quiet
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0].split("#")[0].rstrip("/") or "/"
        if path in ("/", "/analysis", "/comparison", "/analyze", "/compare", "/index.html"):
            return self._send(200, INDEX, "text/html; charset=utf-8")
        if path == "/api/health":
            return self._send(200, json.dumps({"ok": True, "service": "jalli-api", "apiConfigured": True}).encode(), "application/json")
        if path == "/__counts":
            with LOCK:
                return self._send(200, json.dumps(COUNTS).encode(), "application/json")
        return self._send(404, b"not found", "text/plain")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)  # drain
        if self.path == "/api/analyze":
            with LOCK:
                COUNTS["analyze"] += 1
            return self._send(200, anthropic_wrap(ANALYSIS), "application/json")
        if self.path == "/api/compare":
            with LOCK:
                COUNTS["compare"] += 1
            return self._send(200, anthropic_wrap(COMPARISON), "application/json")
        return self._send(404, b"not found", "text/plain")

def start(port=8899):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv

if __name__ == "__main__":
    start()
    threading.Event().wait()
