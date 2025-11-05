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

# Helper function to fix common syntax errors
def fix_syntax_errors(code):
    """Attempt to fix common syntax errors"""
    try:
        # Try to compile first
        compile(code, '<string>', 'exec')
        return code, None
    except SyntaxError as e:
        fixed_code = code
        error_msg = str(e)
        
        # Fix common issues
        # 1. Missing colons
        if "invalid syntax" in error_msg.lower():
            lines = fixed_code.split('\n')
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Add colon to common statements missing it
                if stripped and not stripped.endswith(':') and not stripped.endswith('\\'):
                    for keyword in ['if ', 'elif ', 'else', 'for ', 'while ', 'def ', 'class ', 'try', 'except', 'finally', 'with ']:
                        if stripped.startswith(keyword):
                            # Check if it should have a colon
                            if keyword.strip() in ['else', 'try', 'finally']:
                                lines[i] = line + ':'
                            elif '(' in stripped and ')' in stripped:
                                lines[i] = line + ':'
                            break
            fixed_code = '\n'.join(lines)
        
        # 2. Fix indentation issues
        try:
            import textwrap
            fixed_code = textwrap.dedent(fixed_code)
        except:
            pass
        
        # 3. Remove trailing whitespace
        lines = [line.rstrip() for line in fixed_code.split('\n')]
        fixed_code = '\n'.join(lines)
        
        # Try to compile again
        try:
            compile(fixed_code, '<string>', 'exec')
            return fixed_code, "⚠️ Auto-fixed syntax errors"
        except:
            return code, None
    except Exception:
        return code, None

def safe_process(func):
    """Decorator to safely process code with auto-fix"""
    def wrapper(code):
        # First try to fix any syntax errors
        fixed_code, fix_msg = fix_syntax_errors(code)
        
        try:
            result = func(fixed_code)
            
            # If we fixed something, add a note
            if fix_msg and not result.startswith('❌'):
                result = f"{fix_msg}\n\n{result}"
            
            return result
        except SyntaxError as e:
            return f"❌ Syntax Error: {e}\n\n💡 Tip: Check for missing colons, brackets, or quotes"
        except Exception as e:
            return f"❌ Error: {e}"
    
    return wrapper

# Code optimization functions
@safe_process
def remove_comments(code):
    """Remove comments and blank lines"""
    clean_lines = []
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        clean_lines.append(line.rstrip())
    return '\n'.join(clean_lines) + ('\n' if clean_lines else '')

@safe_process
def beautify_code(code):
    """Beautify with autopep8"""
    if autopep8:
        try:
            return autopep8.fix_code(code, options={'aggressive': 2})
        except Exception as e:
            return f"❌ autopep8 error: {e}"
    return "⚠️ autopep8 not installed"

@safe_process
def black_format(code):
    """Format with Black"""
    if black:
        try:
            return black.format_str(code, mode=black.FileMode())
        except Exception as e:
            return f"❌ Black error: {e}"
    return "⚠️ Black not installed"

@safe_process
def sort_imports(code):
    """Sort imports with isort"""
    if isort:
        try:
            return isort.code(code)
        except Exception as e:
            return f"❌ isort error: {e}"
    return "⚠️ isort not installed"

@safe_process
def remove_docstrings(code):
    """Remove docstrings from code"""
    tree = ast.parse(code)
    
    class DocstringRemover(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            if node.body and isinstance(node.body[0], ast.Expr):
                if isinstance(node.body[0].value, (ast.Str, ast.Constant)):
                    node.body.pop(0)
                    if not node.body:
                        node.body = [ast.Pass()]
            return node
        
        def visit_AsyncFunctionDef(self, node):
            return self.visit_FunctionDef(node)
        
        def visit_ClassDef(self, node):
            self.generic_visit(node)
            if node.body and isinstance(node.body[0], ast.Expr):
                if isinstance(node.body[0].value, (ast.Str, ast.Constant)):
                    node.body.pop(0)
                    if not node.body:
                        node.body = [ast.Pass()]
            return node
    
    new_tree = DocstringRemover().visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)

@safe_process
def minify_code(code):
    """Minify Python code - removes comments, docstrings, and extra whitespace"""
    # First remove comments
    lines = []
    for line in code.splitlines():
        # Remove inline comments but keep strings with #
        if '#' in line:
            in_string = False
            quote_char = None
            for i, char in enumerate(line):
                if char in ('"', "'") and (i == 0 or line[i-1] != '\\'):
                    if not in_string:
                        in_string = True
                        quote_char = char
                    elif char == quote_char:
                        in_string = False
                elif char == '#' and not in_string:
                    line = line[:i]
                    break
        
        stripped = line.rstrip()
        if stripped:
            lines.append(stripped)
    
    code = '\n'.join(lines)
    
    # Remove docstrings using AST
    tree = ast.parse(code)
    
    class MinifyTransformer(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            if node.body and isinstance(node.body[0], ast.Expr):
                if isinstance(node.body[0].value, (ast.Str, ast.Constant)):
                    node.body.pop(0)
                    if not node.body:
                        node.body = [ast.Pass()]
            return node
        
        def visit_AsyncFunctionDef(self, node):
            return self.visit_FunctionDef(node)
        
        def visit_ClassDef(self, node):
            self.generic_visit(node)
            if node.body and isinstance(node.body[0], ast.Expr):
                if isinstance(node.body[0].value, (ast.Str, ast.Constant)):
                    node.body.pop(0)
                    if not node.body:
                        node.body = [ast.Pass()]
            return node
        
        def visit_Module(self, node):
            self.generic_visit(node)
            # Remove module-level docstrings
            if node.body and isinstance(node.body[0], ast.Expr):
                if isinstance(node.body[0].value, (ast.Str, ast.Constant)):
                    node.body.pop(0)
            return node
    
    new_tree = MinifyTransformer().visit(tree)
    ast.fix_missing_locations(new_tree)
    minified = ast.unparse(new_tree)
    
    # Remove excessive blank lines (keep max 1)
    minified = re.sub(r'\n\s*\n\s*\n+', '\n\n', minified)
    
    return minified.strip() + '\n'

def validate_syntax(code):
    """Validate Python syntax with auto-fix attempt"""
    fixed_code, fix_msg = fix_syntax_errors(code)
    
    try:
        compile(fixed_code, '<string>', 'exec')
        if fix_msg:
            return f"{fix_msg}\n✅ Syntax is now valid!"
        return "✅ Syntax is valid!"
    except SyntaxError as e:
        return f"❌ Syntax Error: {e}\n\n💡 Common fixes:\n• Check for missing colons (:)\n• Check brackets matching\n• Check quote marks\n• Check indentation"
    except Exception as e:
        return f"❌ Error: {e}"

def code_stats(code):
    """Generate code statistics"""
    try:
        # Try to fix syntax first
        fixed_code, fix_msg = fix_syntax_errors(code)
        tree = ast.parse(fixed_code)
        
        functions = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        classes = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        imports = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)))
        lines = len(code.splitlines())
        comments = sum(1 for l in code.splitlines() if l.strip().startswith('#'))
        
        stats = f"""📊 Code Statistics

📝 Lines of Code: {lines}
⚙️ Functions: {functions}
🏛 Classes: {classes}
📦 Imports: {imports}
💬 Comment Lines: {comments}
"""
        
        if fix_msg:
            stats = f"{fix_msg}\n\n" + stats
        
        if rcc:
            try:
                complexity = rcc.cc_visit(fixed_code)
                avg_complexity = sum(x.complexity for x in complexity) / (len(complexity) or 1)
                stats += f"🧮 Avg Complexity: {avg_complexity:.2f}\n"
            except:
                pass
        
        return stats
    except Exception as e:
        return f"❌ Stats error: {e}\n\n💡 Make sure your code has valid Python syntax"

@safe_process
def add_try_except(code):
    """Wrap code in basic try-except"""
    wrapped = "try:\n"
    for line in code.splitlines():
        wrapped += "    " + line + "\n"
    wrapped += "except Exception as e:\n    print(f'Error: {e}')\n"
    return wrapped

@safe_process
def add_try_except_detailed(code):
    """Wrap code in try-except with traceback"""
    wrapped = "import traceback\n\ntry:\n"
    for line in code.splitlines():
        wrapped += "    " + line + "\n"
    wrapped += "except Exception as e:\n"
    wrapped += "    print(f'❌ Error occurred: {e}')\n"
    wrapped += "    traceback.print_exc()\n"
    return wrapped

@safe_process
def add_try_except_logging(code):
    """Wrap code in try-except with logging"""
    wrapped = "import logging\nimport traceback\n\n"
    wrapped += "logging.basicConfig(level=logging.ERROR)\nlogger = logging.getLogger(__name__)\n\n"
    wrapped += "try:\n"
    for line in code.splitlines():
        wrapped += "    " + line + "\n"
    wrapped += "except Exception as e:\n"
    wrapped += "    logger.error(f'Error: {e}')\n"
    wrapped += "    logger.error(traceback.format_exc())\n"
    return wrapped

@safe_process
def wrap_functions_try_except(code):
    """Wrap each function in try-except blocks"""
    tree = ast.parse(code)
    
    class FunctionWrapper(ast.NodeTransformer):
        def wrap_function_body(self, node):
            if not node.body:
                return node
            
            # Create try-except wrapper
            try_node = ast.Try(
                body=node.body,
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id='Exception', ctx=ast.Load()),
                        name='e',
                        body=[
                            ast.Expr(
                                value=ast.Call(
                                    func=ast.Name(id='print', ctx=ast.Load()),
                                    args=[
                                        ast.JoinedStr(
                                            values=[
                                                ast.Constant(value=f'Error in {node.name}: '),
                                                ast.FormattedValue(
                                                    value=ast.Name(id='e', ctx=ast.Load()),
                                                    conversion=-1
                                                )
                                            ]
                                        )
                                    ],
                                    keywords=[]
                                )
                            )
                        ]
                    )
                ],
                orelse=[],
                finalbody=[]
            )
            
            node.body = [try_node]
            return node
        
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            return self.wrap_function_body(node)
        
        def visit_AsyncFunctionDef(self, node):
            self.generic_visit(node)
            return self.wrap_function_body(node)
    
    new_tree = FunctionWrapper().visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)

# Helper to detect if message looks like code
def looks_like_code(text):
    """Detect if text looks like Python code"""
    if not text or len(text) < 10:
        return False
    
    # Code indicators
    code_keywords = ['def ', 'class ', 'import ', 'from ', 'return ', 'if __name__', 'print(', '```']
    has_keyword = any(kw in text for kw in code_keywords)
    
    # Check for code structure
    has_indentation = any(line.startswith('    ') or line.startswith('\t') for line in text.split('\n'))
    has_colons = text.count(':') >= 2
    has_parens = '(' in text and ')' in text
    
    # Must have keywords or strong structural indicators
    return has_keyword or (has_indentation and has_colons and has_parens)

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    welcome_msg = """🤖 CODE OPTIMIZER BOT v2.0
by HAZY • @yaplol

✨ Features:
• 🗜️ Minify Code
• 🛡️ Advanced Try-Except Options
• 🔧 Auto-Fix Syntax Errors
• 👥 Works in Groups (reply to code/send files)

📋 Send me:
• Python files (.py)
• Code in messages (direct or reply)
• Works in groups when you reply to code!

Ready to optimize? Send me some code now! 🚀"""
    
    await update.message.reply_text(welcome_msg)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .py file uploads"""
    document = update.message.document
    
    if not document.file_name.endswith('.py'):
        return  # Silently ignore non-Python files
    
    try:
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
            [InlineKeyboardButton("🗜️ Minify", callback_data='minify'),
             InlineKeyboardButton("📄 Remove Docs", callback_data='docstrings')],
            [InlineKeyboardButton("✅ Validate", callback_data='validate'),
             InlineKeyboardButton("📊 Stats", callback_data='stats')],
            [InlineKeyboardButton("🛡️ Try-Except Options ▼", callback_data='tryexcept_menu')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Received {document.file_name} ({len(code)} chars)\n\n🔧 Auto-fix enabled for all operations!\n\nChoose an operation:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error handling document: {e}")
        await update.message.reply_text("❌ Error reading file. Make sure it's a valid Python file!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text code - only respond to code-like messages or in private chats"""
    # Skip if it's a command
    if update.message.text.startswith('/'):
        return
    
    # In group chats, only respond to:
    # 1. Messages that reply to bot's messages
    # 2. Messages that look like code
    # 3. Direct mentions of the bot
    chat_type = update.effective_chat.type
    
    if chat_type in ['group', 'supergroup']:
        is_reply_to_bot = (
            update.message.reply_to_message and 
            update.message.reply_to_message.from_user.id == context.bot.id
        )
        
        bot_mentioned = f"@{context.bot.username}" in update.message.text if context.bot.username else False
        
        # Only process if replying to bot, bot is mentioned, or it really looks like code
        if not (is_reply_to_bot or bot_mentioned or looks_like_code(update.message.text)):
            return
    
    code = update.message.text
    
    # Remove bot mention if present
    if context.bot.username:
        code = code.replace(f"@{context.bot.username}", "").strip()
    
    # Remove code blocks if present
    if code.startswith('```python'):
        code = code.replace('```python', '', 1)
    if code.startswith('```'):
        code = code.replace('```', '', 1)
    if code.endswith('```'):
        code = code.rsplit('```', 1)[0]
    
    code = code.strip()
    
    # Double check if it's actually code after cleaning
    if len(code) < 10 or not looks_like_code(code):
        return
    
    context.user_data['code'] = code
    context.user_data['filename'] = 'code.py'
    
    keyboard = [
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
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Code received ({len(code)} chars)\n\n🔧 Auto-fix enabled for all operations!\n\nChoose an operation:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    # Handle try-except menu
    if query.data == 'tryexcept_menu':
        keyboard = [
            [InlineKeyboardButton("🛡️ Basic Try-Except", callback_data='tryexcept_basic')],
            [InlineKeyboardButton("📝 With Traceback", callback_data='tryexcept_detailed')],
            [InlineKeyboardButton("📋 With Logging", callback_data='tryexcept_logging')],
            [InlineKeyboardButton("⚙️ Wrap Functions", callback_data='tryexcept_functions')],
            [InlineKeyboardButton("◀️ Back to Main Menu", callback_data='back_main')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🛡️ Choose Try-Except Style:\n\n🔧 All options include auto-fix for syntax errors!",
            reply_markup=reply_markup
        )
        return
    
    # Handle back to main menu
    if query.data == 'back_main':
        keyboard = [
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
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Choose an operation:\n\n🔧 Auto-fix enabled for all operations!",
            reply_markup=reply_markup
        )
        return
    
    code = context.user_data.get('code')
    filename = context.user_data.get('filename', 'optimized.py')
    
    if not code:
        await query.edit_message_text("❌ No code found. Please send code first!")
        return
    
    operation = query.data
    await query.edit_message_text(f"⏳ Processing with {operation}...\n\n🔧 Auto-fixing any syntax errors...")
    
    # Execute operation
    operations = {
        'cleanup': remove_comments,
        'beautify': beautify_code,
        'black': black_format,
        'imports': sort_imports,
        'minify': minify_code,
        'docstrings': remove_docstrings,
        'validate': validate_syntax,
        'stats': code_stats,
        'tryexcept_basic': add_try_except,
        'tryexcept_detailed': add_try_except_detailed,
        'tryexcept_logging': add_try_except_logging,
        'tryexcept_functions': wrap_functions_try_except,
    }
    
    func = operations.get(operation)
    if not func:
        await query.edit_message_text("❌ Unknown operation")
        return
    
    try:
        result = func(code)
        
        # For stats and validation, just show text
        if operation in ['validate', 'stats']:
            await query.edit_message_text(result)
            return
        
        # Send optimized code as file
        if result and not result.startswith('❌') and not result.startswith('⚠️'):
            bio = BytesIO(result.encode('utf-8'))
            bio.name = f"optimized_{filename}"
            
            original_size = len(code)
            new_size = len(result)
            reduction = ((original_size - new_size) / original_size * 100) if original_size > 0 else 0
            
            caption = f"✅ Operation: {operation}\n📁 File: {bio.name}\n"
            caption += f"📏 Original: {original_size} chars\n"
            caption += f"📏 New: {new_size} chars\n"
            
            if operation == 'minify' and reduction > 0:
                caption += f"🗜️ Reduced by: {reduction:.1f}%"
            
            await query.message.reply_document(
                document=bio,
                filename=bio.name,
                caption=caption
            )
            await query.edit_message_text(f"✅ Optimization complete! Check the file above.")
        else:
            await query.edit_message_text(result)
            
    except Exception as e:
        logger.error(f"Error in button callback: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_text = """🆘 HELP - How to Use

Send Code:
• Upload a .py file
• Paste code directly in private chat
• In groups: Reply to code or mention bot

Operations:
🔥 Cleanup - Remove comments & blank lines
✨ Beautify - Auto-format with autopep8
⚫ Black Format - Format with Black
📦 Sort Imports - Organize imports with isort
🗜️ Minify - Compress code (remove docs, comments, whitespace)
📄 Remove Docstrings - Strip all docstrings
✅ Validate Syntax - Check for syntax errors
📊 Code Stats - Get code metrics

🛡️ Try-Except Options:
• Basic - Simple try-except wrapper
• With Traceback - Detailed error info
• With Logging - Professional logging
• Wrap Functions - Add try-except to each function

🔧 Auto-Fix Feature:
• All operations automatically attempt to fix common syntax errors
• Adds missing colons
• Fixes indentation issues
• Reports what was fixed

👥 Group Chat Usage:
• Bot only responds to code (won't spam chat)
• Reply to code messages
• Or mention @botname with your code
• Upload .py files directly

Tips:
• Works with any Python code
• Results sent as .py files
• Minify can reduce file size significantly!
• Auto-fix helps with broken code

Need help? Just ask! 🚀"""
    
    await update.message.reply_text(help_text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

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
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    logger.info("🤖 Bot started successfully!")
    
    # Run bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
