import os
import sys
import logging
import ast
import textwrap
import subprocess
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from flask import Flask
from threading import Thread

# Install dependencies
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

try:
    import black
except:
    black = None

try:
    import autopep8
except:
    autopep8 = None

try:
    import isort
except:
    isort = None

try:
    import radon.complexity as rcc
except:
    rcc = None

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for health checks (Render & UptimeRobot)
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

# Code optimization functions
def remove_comments(code):
    """Remove comments and blank lines"""
    clean_lines = []
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        clean_lines.append(line.rstrip())
    return '\n'.join(clean_lines) + ('\n' if clean_lines else '')

def beautify_code(code):
    """Beautify with autopep8"""
    if autopep8:
        try:
            return autopep8.fix_code(code)
        except Exception as e:
            return f"❌ autopep8 error: {e}"
    return "⚠️ autopep8 not installed"

def black_format(code):
    """Format with Black"""
    if black:
        try:
            return black.format_str(code, mode=black.FileMode())
        except Exception as e:
            return f"❌ Black error: {e}"
    return "⚠️ Black not installed"

def sort_imports(code):
    """Sort imports with isort"""
    if isort:
        try:
            return isort.code(code)
        except Exception as e:
            return f"❌ isort error: {e}"
    return "⚠️ isort not installed"

def remove_docstrings(code):
    """Remove docstrings from code"""
    try:
        tree = ast.parse(code)
        
        class DocstringRemover(ast.NodeTransformer):
            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                if node.body and isinstance(node.body[0], ast.Expr):
                    if isinstance(node.body[0].value, (ast.Str, ast.Constant)):
                        node.body.pop(0)
                return node
            
            def visit_AsyncFunctionDef(self, node):
                return self.visit_FunctionDef(node)
            
            def visit_ClassDef(self, node):
                self.generic_visit(node)
                if node.body and isinstance(node.body[0], ast.Expr):
                    if isinstance(node.body[0].value, (ast.Str, ast.Constant)):
                        node.body.pop(0)
                return node
        
        new_tree = DocstringRemover().visit(tree)
        ast.fix_missing_locations(new_tree)
        return ast.unparse(new_tree)
    except Exception as e:
        return f"❌ Docstring removal error: {e}"

def validate_syntax(code):
    """Validate Python syntax"""
    try:
        compile(code, '<string>', 'exec')
        return "✅ Syntax is valid!"
    except Exception as e:
        return f"❌ Syntax error: {e}"

def code_stats(code):
    """Generate code statistics"""
    try:
        tree = ast.parse(code)
        functions = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        classes = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        imports = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)))
        lines = len(code.splitlines())
        comments = sum(1 for l in code.splitlines() if l.strip().startswith('#'))
        
        stats = f"""📊 **Code Statistics**

📝 Lines of Code: {lines}
⚙️ Functions: {functions}
🏛 Classes: {classes}
📦 Imports: {imports}
💬 Comment Lines: {comments}
"""
        
        if rcc:
            try:
                complexity = rcc.cc_visit(code)
                avg_complexity = sum(x.complexity for x in complexity) / (len(complexity) or 1)
                stats += f"🧮 Avg Complexity: {avg_complexity:.2f}\n"
            except:
                pass
        
        return stats
    except Exception as e:
        return f"❌ Stats error: {e}"

def add_try_except(code):
    """Wrap code in try-except"""
    wrapped = "try:\n"
    for line in code.splitlines():
        wrapped += "    " + line + "\n"
    wrapped += "except Exception as e:\n    import traceback\n    traceback.print_exc()\n"
    return wrapped

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    keyboard = [
        [InlineKeyboardButton("🔥 Ultimate Cleanup", callback_data='cleanup')],
        [InlineKeyboardButton("✨ Beautify (autopep8)", callback_data='beautify')],
        [InlineKeyboardButton("⚫ Black Format", callback_data='black')],
        [InlineKeyboardButton("📦 Sort Imports", callback_data='imports')],
        [InlineKeyboardButton("📄 Remove Docstrings", callback_data='docstrings')],
        [InlineKeyboardButton("✅ Validate Syntax", callback_data='validate')],
        [InlineKeyboardButton("📊 Code Stats", callback_data='stats')],
        [InlineKeyboardButton("🛡 Add Try-Except", callback_data='tryexcept')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = """🤖 CODE OPTIMIZER BOT
by HAZY • @yaplol
Ready to optimize? Send me some code! 🚀"""
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .py file uploads"""
    document = update.message.document
    
    if not document.file_name.endswith('.py'):
        await update.message.reply_text("❌ Please send a .py file!")
        return
    
    file = await context.bot.get_file(document.file_id)
    file_bytes = await file.download_as_bytearray()
    code = file_bytes.decode('utf-8')
    
    context.user_data['code'] = code
    context.user_data['filename'] = document.file_name
    
    keyboard = [
        [InlineKeyboardButton("🔥 Cleanup", callback_data='cleanup'),
         InlineKeyboardButton("✨ Beautify", callback_data='beautify')],
        [InlineKeyboardButton("⚫ Black", callback_data='black'),
         InlineKeyboardButton("📦 Imports", callback_data='imports')],
        [InlineKeyboardButton("📄 Remove Docs", callback_data='docstrings'),
         InlineKeyboardButton("✅ Validate", callback_data='validate')],
        [InlineKeyboardButton("📊 Stats", callback_data='stats'),
         InlineKeyboardButton("🛡 Try-Except", callback_data='tryexcept')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Received {document.file_name} ({len(code)} chars)\n\nChoose an operation:",
        reply_markup=reply_markup
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text code"""
    code = update.message.text
    
    # Ignore commands
    if code.startswith('/'):
        return
    
    context.user_data['code'] = code
    context.user_data['filename'] = 'code.py'
    
    keyboard = [
        [InlineKeyboardButton("🔥 Cleanup", callback_data='cleanup'),
         InlineKeyboardButton("✨ Beautify", callback_data='beautify')],
        [InlineKeyboardButton("⚫ Black", callback_data='black'),
         InlineKeyboardButton("📦 Imports", callback_data='imports')],
        [InlineKeyboardButton("📄 Remove Docs", callback_data='docstrings'),
         InlineKeyboardButton("✅ Validate", callback_data='validate')],
        [InlineKeyboardButton("📊 Stats", callback_data='stats'),
         InlineKeyboardButton("🛡 Try-Except", callback_data='tryexcept')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Code received ({len(code)} chars)\n\nChoose an operation:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    code = context.user_data.get('code')
    filename = context.user_data.get('filename', 'optimized.py')
    
    if not code:
        await query.edit_message_text("❌ No code found. Please send code first!")
        return
    
    operation = query.data
    await query.edit_message_text(f"⏳ Processing with **{operation}**...", parse_mode='Markdown')
    
    # Execute operation
    operations = {
        'cleanup': remove_comments,
        'beautify': beautify_code,
        'black': black_format,
        'imports': sort_imports,
        'docstrings': remove_docstrings,
        'validate': validate_syntax,
        'stats': code_stats,
        'tryexcept': add_try_except
    }
    
    func = operations.get(operation)
    if not func:
        await query.edit_message_text("❌ Unknown operation")
        return
    
    try:
        result = func(code)
        
        # For stats and validation, just show text
        if operation in ['validate', 'stats']:
            await query.edit_message_text(result, parse_mode='Markdown')
            return
        
        # Send optimized code as file
        if result and not result.startswith('❌') and not result.startswith('⚠️'):
            bio = BytesIO(result.encode('utf-8'))
            bio.name = f"optimized_{filename}"
            
            await query.message.reply_document(
                document=bio,
                filename=bio.name,
                caption=f"✅ **Operation:** {operation}\n📁 **File:** {bio.name}\n📏 **Size:** {len(result)} chars",
                parse_mode='Markdown'
            )
            await query.edit_message_text(f"✅ Optimization complete! Check the file above.")
        else:
            await query.edit_message_text(result)
            
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_text = """🆘 **HELP - How to Use**

**Send Code:**
• Upload a .py file
• Or paste code directly

**Operations:**
🔥 **Ultimate Cleanup** - Remove comments & blank lines
✨ **Beautify** - Auto-format with autopep8
⚫ **Black Format** - Format with Black
📦 **Sort Imports** - Organize imports with isort
📄 **Remove Docstrings** - Strip all docstrings
✅ **Validate Syntax** - Check for syntax errors
📊 **Code Stats** - Get code metrics
🛡 **Try-Except** - Wrap in error handler

**Tips:**
• Works with any Python code
• Results sent as .py files
• Stats shown as text

Need help? Just ask! 🚀"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """Start the bot"""
    TOKEN = "7697666723:AAGRF1gv8DGI6P8vU_cWYc_2m26CAifya-E"
    
    # Start Flask in background thread for health checks
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Flask health check server started")
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("🤖 Bot started successfully!")
    
    # Run bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
