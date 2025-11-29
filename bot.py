import os
import sys
import logging
import ast
import textwrap
import subprocess
import re
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from flask import Flask
from threading import Thread

REQUIRED_CHANNEL_ID = -1003419302071
REQUIRED_CHANNEL_LINK = "https://t.me/+JJkGhk64acczNjI9"

def install(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

for pkg in ['python-telegram-bot', 'flask', 'black', 'autopep8', 'isort', 'radon']:
    try:
        install(pkg)
    except:
        pass

try: import black
except: black = None
try: import autopep8
except: autopep8 = None
try: import isort
except: isort = None
try: import radon.complexity as rcc
except: rcc = None

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive! 🤖✅", 200

@app.route('/health')
def health():
    return {"status": "healthy", "bot": "running"}, 200

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

async def is_user_member(bot, user_id):
    try:
        m = await bot.get_chat_member(REQUIRED_CHANNEL_ID, user_id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

def fix_syntax_errors(code):
    try:
        compile(code, '<string>', 'exec')
        return code, None
    except SyntaxError as e:
        fixed = code
        msg = str(e)
        if "invalid syntax" in msg.lower():
            lines = fixed.split('\n')
            for i, line in enumerate(lines):
                s = line.strip()
                if s and not s.endswith(':') and not s.endswith('\\'):
                    for k in ['if ', 'elif ', 'else', 'for ', 'while ', 'def ', 'class ', 'try', 'except', 'finally', 'with ']:
                        if s.startswith(k):
                            if k.strip() in ['else', 'try', 'finally']:
                                lines[i] = line + ':'
                            elif '(' in s and ')' in s:
                                lines[i] = line + ':'
                            break
            fixed = '\n'.join(lines)
        try:
            fixed = textwrap.dedent(fixed)
        except:
            pass
        lines = [l.rstrip() for l in fixed.split('\n')]
        fixed = '\n'.join(lines)
        try:
            compile(fixed, '<string>', 'exec')
            return fixed, "⚠️ Auto-fixed syntax errors"
        except:
            return code, None
    except:
        return code, None

def safe_process(f):
    def w(code):
        fixed, msg = fix_syntax_errors(code)
        try:
            r = f(fixed)
            if msg and not r.startswith('❌'):
                r = f"{msg}\n\n{r}"
            return r
        except SyntaxError as e:
            return f"❌ Syntax Error: {e}"
        except Exception as e:
            return f"❌ Error: {e}"
    return w

@safe_process
def remove_comments(code):
    out = []
    for l in code.splitlines():
        s = l.strip()
        if not s or s.startswith('#'):
            continue
        out.append(l.rstrip())
    return '\n'.join(out) + ('\n' if out else '')

@safe_process
def beautify_code(code):
    if autopep8:
        try: return autopep8.fix_code(code, options={'aggressive': 2})
        except Exception as e: return f"❌ autopep8 error: {e}"
    return "⚠️ autopep8 not installed"

@safe_process
def black_format(code):
    if black:
        try: return black.format_str(code, mode=black.FileMode())
        except Exception as e: return f"❌ Black error: {e}"
    return "⚠️ Black not installed"

@safe_process
def sort_imports(code):
    if isort:
        try: return isort.code(code)
        except Exception as e: return f"❌ isort error: {e}"
    return "⚠️ isort not installed"

@safe_process
def remove_docstrings(code):
    t = ast.parse(code)
    class R(ast.NodeTransformer):
        def visit_FunctionDef(self, n):
            self.generic_visit(n)
            if n.body and isinstance(n.body[0], ast.Expr):
                if isinstance(n.body[0].value, (ast.Str, ast.Constant)):
                    n.body.pop(0)
                    if not n.body: n.body=[ast.Pass()]
            return n
        def visit_AsyncFunctionDef(self, n): return self.visit_FunctionDef(n)
        def visit_ClassDef(self, n):
            self.generic_visit(n)
            if n.body and isinstance(n.body[0], ast.Expr):
                if isinstance(n.body[0].value, (ast.Str, ast.Constant)):
                    n.body.pop(0)
                    if not n.body: n.body=[ast.Pass()]
            return n
    nt = R().visit(t)
    ast.fix_missing_locations(nt)
    return ast.unparse(nt)

@safe_process
def minify_code(code):
    lines = []
    for l in code.splitlines():
        if '#' in l:
            ins = False
            qc = None
            for i,c in enumerate(l):
                if c in ('"',"'") and (i==0 or l[i-1]!="\\"):
                    if not ins:
                        ins=True; qc=c
                    elif c==qc:
                        ins=False
                elif c=='#' and not ins:
                    l=l[:i]; break
        s=l.rstrip()
        if s: lines.append(s)
    code='\n'.join(lines)
    t=ast.parse(code)
    class T(ast.Node.NodeTransformer):
        pass
    class T(ast.NodeTransformer):
        def visit_FunctionDef(self,n):
            self.generic_visit(n)
            if n.body and isinstance(n.body[0],ast.Expr):
                if isinstance(n.body[0].value,(ast.Str,ast.Constant)):
                    n.body.pop(0)
                    if not n.body: n.body=[ast.Pass()]
            return n
        def visit_AsyncFunctionDef(self,n): return self.visit_FunctionDef(n)
        def visit_ClassDef(self,n):
            self.generic_visit(n)
            if n.body and isinstance(n.body[0],ast.Expr):
                if isinstance(n.body[0].value,(ast.Str,ast.Constant)):
                    n.body.pop(0)
                    if not n.body: n.body=[ast.Pass()]
            return n
        def visit_Module(self,n):
            self.generic_visit(n)
            if n.body and isinstance(n.body[0],ast.Expr):
                if isinstance(n.body[0].value,(ast.Str,ast.Constant)):
                    n.body.pop(0)
            return n
    nt=T().visit(t)
    ast.fix_missing_locations(nt)
    s=ast.unparse(nt)
    s=re.sub(r'\n\s*\n\s*\n+','\n\n',s)
    return s.strip()+'\n'

def validate_syntax(code):
    f,m=fix_syntax_errors(code)
    try:
        compile(f,'<string>','exec')
        return f"{m+'\n' if m else ''}✅ Syntax is valid!"
    except SyntaxError as e:
        return f"❌ Syntax Error: {e}"
    except Exception as e:
        return f"❌ Error: {e}"

def code_stats(code):
    try:
        f,m=fix_syntax_errors(code)
        t=ast.parse(f)
        funcs=sum(1 for n in ast.walk(t) if isinstance(n,ast.FunctionDef))
        classes=sum(1 for n in ast.walk(t) if isinstance(n,ast.ClassDef))
        imps=sum(1 for n in ast.walk(t) if isinstance(n,(ast.Import,ast.ImportFrom)))
        lines=len(code.splitlines())
        cm=sum(1 for l in code.splitlines() if l.strip().startswith('#'))
        s=f"""📊 Code Statistics

📝 Lines of Code: {lines}
⚙️ Functions: {funcs}
🏛 Classes: {classes}
📦 Imports: {imps}
💬 Comment Lines: {cm}
"""
        if m: s=m+"\n\n"+s
        if rcc:
            try:
                c=rcc.cc_visit(f)
                a=sum(x.complexity for x in c)/(len(c) or 1)
                s+=f"🧮 Avg Complexity: {a:.2f}\n"
            except:
                pass
        return s
    except Exception as e:
        return f"❌ Stats error: {e}"

@safe_process
def add_try_except(code):
    w="try:\n"
    for l in code.splitlines(): w+="    "+l+"\n"
    w+="except Exception as e:\n    print(f'Error: {e}')\n"
    return w

@safe_process
def add_try_except_detailed(code):
    w="import traceback\n\ntry:\n"
    for l in code.splitlines(): w+="    "+l+"\n"
    w+="except Exception as e:\n    print(f'❌ Error occurred: {e}')\n    traceback.print_exc()\n"
    return w

@safe_process
def add_try_except_logging(code):
    w="import logging\nimport traceback\n\nlogging.basicConfig(level=logging.ERROR)\nlogger=logging.getLogger(__name__)\n\ntry:\n"
    for l in code.splitlines(): w+="    "+l+"\n"
    w+="except Exception as e:\n    logger.error(f'Error: {e}')\n    logger.error(traceback.format_exc())\n"
    return w

@safe_process
def wrap_functions_try_except(code):
    t=ast.parse(code)
    class W(ast.NodeTransformer):
        def wrap(self,n):
            if not n.body: return n
            tr=ast.Try(
                body=n.body,
                handlers=[ast.ExceptHandler(
                    type=ast.Name(id='Exception',ctx=ast.Load()),
                    name='e',
                    body=[ast.Expr(value=ast.Call(func=ast.Name(id='print',ctx=ast.Load()),
                        args=[ast.JoinedStr(values=[
                            ast.Constant(value=f'Error in {n.name}: '),
                            ast.FormattedValue(value=ast.Name(id='e',ctx=ast.Load()),conversion=-1)])],
                        keywords=[]))])],
                orelse=[],finalbody=[])
            n.body=[tr]
            return n
        def visit_FunctionDef(self,n): self.generic_visit(n); return self.wrap(n)
        def visit_AsyncFunctionDef(self,n): self.generic_visit(n); return self.wrap(n)
    nt=W().visit(t)
    ast.fix_missing_locations(nt)
    return ast.unparse(nt)

def looks_like_code(t):
    if not t or len(t)<10: return False
    kws=['def ','class ','import ','from ','return ','if __name__','print(','```']
    kw=any(k in t for k in kws)
    ind=any(l.startswith('    ') or l.startswith('\t') for l in t.split('\n'))
    col=t.count(':')>=2
    par='(' in t and ')' in t
    return kw or (ind and col and par)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user.id
    bot=context.bot
    if not await is_user_member(bot,user):
        btn=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=REQUIRED_CHANNEL_LINK)]])
        await update.message.reply_text(
            "🚫 You must join our channel to use this bot.\n\nJoin here:",
            reply_markup=btn)
        return
    msg="""🤖 CODE OPTIMIZER BOT v1.0
by HAZY • @yaplol

✨ Features at /help

Ready to optimize? Send me some code now! 🚀"""
    await update.message.reply_text(msg)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user.id
    bot=context.bot
    if not await is_user_member(bot,user):
        btn=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=REQUIRED_CHANNEL_LINK)]])
        await update.message.reply_text(
            "🚫 You must join our channel to use this bot.\n\nJoin here:",
            reply_markup=btn)
        return

    d=update.message.document
    if not d.file_name.endswith('.py'): return
    try:
        f=await context.bot.get_file(d.file_id)
        b=await f.download_as_bytearray()
        code=b.decode('utf-8')
        context.user_data['code']=code
        context.user_data['filename']=d.file_name
        kb=[
            [InlineKeyboardButton("🔥 Cleanup", callback_data='cleanup'),
             InlineKeyboardButton("✨ Beautify", callback_data='beautify')],
            [InlineKeyboardButton("⚫ Black", callback_data='black'),
             InlineKeyboardButton("📦 Imports", callback_data='imports')],
            [InlineKeyboardButton("🗜️ Minify", callback_data='minify'),
             InlineKeyboardButton("📄 Remove Docs", callback_data='docstrings')],
            [InlineKeyboardButton("✅ Validate", callback_data='validate'),
             InlineKeyboardButton("📊 Stats", callback_data='stats')],
            [InlineKeyboardButton("🛡️ Try-Except Options ▼", callback_data='tryexcept_menu')],
        ]
        rm=InlineKeyboardMarkup(kb)
        await update.message.reply_text(
            f"✅ Received {d.file_name} ({len(code)} chars)\n\nChoose an operation:",
            reply_markup=rm)
    except:
        await update.message.reply_text("❌ Error reading file.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.startswith('/'): return
    user=update.effective_user.id
    bot=context.bot

    if not await is_user_member(bot,user):
        btn=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=REQUIRED_CHANNEL_LINK)]])
        await update.message.reply_text(
            "🚫 You must join our channel to use this bot.\n\nJoin here:",
            reply_markup=btn)
        return

    t=update.message.text
    ct=update.effective_chat.type

    if ct in ['group','supergroup']:
        r=update.message.reply_to_message and update.message.reply_to_message.from_user.id==context.bot.id
        m=context.bot.username and f"@{context.bot.username}" in t
        if not (r or m or looks_like_code(t)): return

    code=t
    if context.bot.username:
        code=code.replace(f"@{context.bot.username}","").strip()
    if code.startswith('```python'): code=code.replace('```python','',1)
    if code.startswith('```'): code=code.replace('```','',1)
    if code.endswith('```'): code=code.rsplit('```',1)[0]
    code=code.strip()
    if len(code)<10 or not looks_like_code(code): return

    context.user_data['code']=code
    context.user_data['filename']='code.py'

    kb=[
        [InlineKeyboardButton("🔥 Cleanup", callback_data='cleanup'),
         InlineKeyboardButton("✨ Beautify", callback_data='beautify')],
        [InlineKeyboardButton("⚫ Black", callback_data='black'),
         InlineKeyboardButton("📦 Imports", callback_data='imports')],
        [InlineKeyboardButton("🗜️ Minify", callback_data='minify'),
         InlineKeyboardButton("📄 Remove Docs", callback_data='docstrings')],
        [InlineKeyboardButton("✅ Validate", callback_data='validate'),
         InlineKeyboardButton("📊 Stats", callback_data='stats')],
        [InlineKeyboardButton("🛡️ Try-Except Options ▼", callback_data='tryexcept_menu')],
    ]
    rm=InlineKeyboardMarkup(kb)

    await update.message.reply_text(
        f"✅ Code received ({len(code)} chars)\n\nChoose an operation:",
        reply_markup=rm)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()

    user=q.from_user.id
    bot=context.bot

    if not await is_user_member(bot,user):
        btn=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=REQUIRED_CHANNEL_LINK)]])
        await q.edit_message_text(
            "🚫 You must join our channel to use this bot.\n\nJoin here:",
            reply_markup=btn)
        return

    if q.data=="tryexcept_menu":
        kb=[
            [InlineKeyboardButton("🛡️ Basic Try-Except", callback_data='tryexcept_basic')],
            [InlineKeyboardButton("📝 With Traceback", callback_data='tryexcept_detailed')],
            [InlineKeyboardButton("📋 With Logging", callback_data='tryexcept_logging')],
            [InlineKeyboardButton("⚙️ Wrap Functions", callback_data='tryexcept_functions')],
            [InlineKeyboardButton("◀️ Back to Main Menu", callback_data='back_main')],
        ]
        rm=InlineKeyboardMarkup(kb)
        await q.edit_message_text("🛡️ Choose Try-Except Style:", reply_markup=rm)
        return

    if q.data=="back_main":
        kb=[
            [InlineKeyboardButton("🔥 Cleanup", callback_data='cleanup'),
             InlineKeyboardButton("✨ Beautify", callback_data='beautify')],
            [InlineKeyboardButton("⚫ Black", callback_data='black'),
             InlineKeyboardButton("📦 Imports", callback_data='imports')],
            [InlineKeyboardButton("🗜️ Minify", callback_data='minify'),
             InlineKeyboardButton("📄 Remove Docs", callback_data='docstrings')],
            [InlineKeyboardButton("✅ Validate", callback_data='validate'),
             InlineKeyboardButton("📊 Stats", callback_data='stats')],
            [InlineKeyboardButton("🛡️ Try-Except Options ▼", callback_data='tryexcept_menu')],
        ]
        rm=InlineKeyboardMarkup(kb)
        await q.edit_message_text("Choose an operation:", reply_markup=rm)
        return

    code=context.user_data.get('code')
    filename=context.user_data.get('filename','optimized.py')

    if not code:
        await q.edit_message_text("❌ No code found. Please send code first!")
        return

    await q.edit_message_text(f"⏳ Processing...")

    ops={
        'cleanup':remove_comments,
        'beautify':beautify_code,
        'black':black_format,
        'imports':sort_imports,
        'minify':minify_code,
        'docstrings':remove_docstrings,
        'validate':validate_syntax,
        'stats':code_stats,
        'tryexcept_basic':add_try_except,
        'tryexcept_detailed':add_try_except_detailed,
        'tryexcept_logging':add_try_except_logging,
        'tryexcept_functions':wrap_functions_try_except,
    }

    func=ops.get(q.data)
    if not func:
        await q.edit_message_text("❌ Unknown operation")
        return

    try:
        result=func(code)

        if q.data in ['validate','stats']:
            await q.edit_message_text(result)
            return

        if result and not result.startswith(('❌','⚠️')):
            bio=BytesIO(result.encode('utf-8'))
            bio.name=f"optimized_{filename}"
            os=len(code)
            ns=len(result)
            r=((os-ns)/os*100) if os>0 else 0
            c=f"✅ Operation: {q.data}\n📁 File: {bio.name}\n📏 Original: {os} chars\n📏 New: {ns} chars\n"
            if q.data=='minify' and r>0: c+=f"🗜️ Reduced by: {r:.1f}%"
            await q.message.reply_document(document=bio, filename=bio.name, caption=c)
            await q.edit_message_text("✅ Optimization complete!")
        else:
            await q.edit_message_text(result)

    except Exception as e:
        await q.edit_message_text(f"❌ Error: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user.id
    bot=context.bot
    if not await is_user_member(bot,user):
        btn=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=REQUIRED_CHANNEL_LINK)]])
        await update.message.reply_text(
            "🚫 You must join our channel to use this bot.\n\nJoin here:",
            reply_markup=btn)
        return

    h="""🔥 Cleanup: Remove comments & blanks
✨ Beautify: Format with autopep8
⚫ Black: Format with Black
📦 Imports: Sort imports
🗜️ Minify: Compress code
📄 Remove Docs: Strip docstrings
✅ Validate: Check syntax
📊 Stats: Code metrics
🛡️ Try-Except: Add error handling
"""
    await update.message.reply_text(h)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

def main():
    TOKEN = "8555445957:AAFPOfR8a2deXyb4ag3B9yfLN4X3AU9BtbI"
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
