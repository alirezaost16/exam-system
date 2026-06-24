#!/bin/bash
# ════════════════════════════════════════════════
#  سامانه آزمون آنلاین — اسکریپت راه‌اندازی
# ════════════════════════════════════════════════

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║     سامانه آزمون آنلاین              ║"
echo "  ║     Online Exam System v1.0          ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 یافت نشد. لطفاً Python 3.9+ نصب کنید."
    exit 1
fi

echo "✅ Python: $(python3 --version)"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 ایجاد محیط مجازی..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "📥 نصب وابستگی‌ها..."
pip install -r requirements.txt -q

echo ""
echo "🚀 راه‌اندازی سرور روی http://localhost:8000"
echo ""
echo "  اطلاعات ورود پیش‌فرض:"
echo "  ─────────────────────────────────"
echo "  👤 مدیر:   admin     / admin123"
echo "  🎓 استاد:  teacher1  / teacher123"
echo "  📚 دانشجو: student1  / student123"
echo "  ─────────────────────────────────"
echo ""

# Run server
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
