# copyright 2020-22 @Mohamed Rizad
# Telegram @riz4d
# Instagram @riz.4d
from pyrogram import *
import requests as re
from Config import *
from pyrogram.types import InlineKeyboardButton,InlineKeyboardMarkup
import wget
import os
import psycopg2
from psycopg2.extras import RealDictCursor 

buttons=InlineKeyboardMarkup(
                             [
                             [
            InlineKeyboardButton('📧 Generate New', callback_data='generate'),
            InlineKeyboardButton('🔄 Refresh', callback_data='refresh')
                   ],
                   [
            InlineKeyboardButton('💾 Save Email', callback_data='save_email'),
            InlineKeyboardButton('📋 My Emails', callback_data='list_emails')
                   ],
                   [
            InlineKeyboardButton('❌ Close', callback_data='close')
                   ] 
                             ])

msg_buttons=InlineKeyboardMarkup(
                             [
                             [
            InlineKeyboardButton('📖 View Message', callback_data='view_msg'),
            InlineKeyboardButton('🔄 Refresh', callback_data='refresh')
                   ],
                   [
            InlineKeyboardButton('❌ Close', callback_data='close')
                   ] 
                             ])


app=Client('Temp-Mail Bot',
           api_id=API_ID,
           api_hash=API_HASH,
           bot_token=BOT_TOKEN)

user_sessions = {}

def get_db_connection():
    return psycopg2.connect(os.environ['DATABASE_URL'])

def generate_guerrilla():
    try:
        resp = re.get("https://api.guerrillamail.com/ajax.php?f=get_email_address&ip=127.0.0.1&agent=Mozilla", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and 'email_addr' in data and 'sid_token' in data:
                return {
                    'email': data['email_addr'],
                    'sid_token': data['sid_token'],
                    'alias': data.get('alias', '')
                }
        return None
    except Exception as e:
        print(f"Error generating Guerrilla Mail: {e}")
        return None

def check_guerrilla_messages(sid_token):
    try:
        resp = re.get(f"https://api.guerrillamail.com/ajax.php?f=check_email&sid_token={sid_token}&seq=0", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'list' in data:
                return data['list']
        return []
    except Exception as e:
        print(f"Error checking Guerrilla Mail messages: {e}")
        return []

def read_guerrilla_message(sid_token, mail_id):
    try:
        resp = re.get(f"https://api.guerrillamail.com/ajax.php?f=fetch_email&sid_token={sid_token}&email_id={mail_id}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"Error reading Guerrilla Mail message: {e}")
        return None

def get_service_info(service):
    service_map = {
        'guerrilla': {'name': 'Guerrilla Mail', 'icon': '⚡'},
        'dropmail': {'name': 'DropMail', 'icon': '📬'},
        'mailtm': {'name': 'Mail.tm', 'icon': '🔐'}
    }
    return service_map.get(service, {'name': 'Mail.tm', 'icon': '🔐'})

def generate_dropmail_token(user_id):
    import hashlib
    import time
    unique_str = f"dropmail_{user_id}_{int(time.time())}"
    return hashlib.md5(unique_str.encode()).hexdigest()[:16]

def generate_dropmail():
    try:
        token = generate_dropmail_token(os.urandom(8).hex())
        graphql_query = {
            "query": "mutation { introduceSession { id expiresAt addresses { address } } }"
        }
        resp = re.post(f"https://dropmail.me/api/graphql/{token}", 
                       json=graphql_query, 
                       timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and 'introduceSession' in data['data']:
                session_data = data['data']['introduceSession']
                if session_data and 'addresses' in session_data and len(session_data['addresses']) > 0:
                    return {
                        'email': session_data['addresses'][0]['address'],
                        'session_id': session_data['id'],
                        'token': token,
                        'expires_at': session_data.get('expiresAt', '')
                    }
        return None
    except Exception as e:
        print(f"Error generating DropMail: {e}")
        return None

def check_dropmail_messages(token, session_id):
    try:
        graphql_query = {
            "query": f'query {{ session(id: "{session_id}") {{ mails {{ id fromAddr toAddr headerSubject text }} }} }}'
        }
        resp = re.post(f"https://dropmail.me/api/graphql/{token}", 
                       json=graphql_query, 
                       timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and 'session' in data['data'] and data['data']['session']:
                return data['data']['session'].get('mails', [])
        return []
    except Exception as e:
        print(f"Error checking DropMail messages: {e}")
        return []

def read_dropmail_message(token, session_id, mail_id):
    try:
        graphql_query = {
            "query": f'query {{ session(id: "{session_id}") {{ mails {{ id fromAddr toAddr headerSubject text html downloadUrl }} }} }}'
        }
        resp = re.post(f"https://dropmail.me/api/graphql/{token}", 
                       json=graphql_query, 
                       timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and 'session' in data['data'] and data['data']['session']:
                mails = data['data']['session'].get('mails', [])
                for mail in mails:
                    if mail['id'] == mail_id:
                        return mail
        return None
    except Exception as e:
        print(f"Error reading DropMail message: {e}")
        return None

def init_database():
    """Initialize database tables on startup - ensures tables exist"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create saved_emails table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS saved_emails (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                email_name VARCHAR(100) NOT NULL,
                email_address VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL,
                email_service VARCHAR(50) DEFAULT 'mailtm',
                session_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, email_name)
            )
        """)
        
        # Create users table to track all interactions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(100),
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                first_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_interactions INTEGER DEFAULT 1
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False

def log_user(user):
    """Log user interaction - creates new user or updates last interaction"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, first_interaction, last_interaction, total_interactions)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                last_interaction = CURRENT_TIMESTAMP,
                total_interactions = users.total_interactions + 1
        """, (user.id, user.username, user.first_name, user.last_name))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error logging user: {e}")
        return False

def save_email_to_db(user_id, name, email, password, email_service='mailtm', session_id=None):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO saved_emails (user_id, email_name, email_address, password, email_service, session_id) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (user_id, email_name) DO UPDATE SET email_address = %s, password = %s, email_service = %s, session_id = %s",
            (user_id, name, email, password, email_service, session_id, email, password, email_service, session_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving email to DB: {e}")
        return False

def get_saved_emails(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT email_name, email_address, email_service FROM saved_emails WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        emails = cur.fetchall()
        cur.close()
        conn.close()
        return emails
    except Exception as e:
        print(f"Error getting saved emails: {e}")
        return []

def load_email_from_db(user_id, name):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT email_address, password, email_service, session_id FROM saved_emails WHERE user_id = %s AND email_name = %s", (user_id, name))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Error loading email from DB: {e}")
        return None

def delete_email_from_db(user_id, name):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM saved_emails WHERE user_id = %s AND email_name = %s", (user_id, name))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        return deleted
    except Exception as e:
        print(f"Error deleting email from DB: {e}")
        return False

@app.on_message(filters.command('start'))
async def start_msg(client,message):
    user_id = message.from_user.id
    
    # Track user interaction
    log_user(message.from_user)
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {'email': '', 'auth_token': None, 'idnum': None, 'saved_emails': {}, 'password': '', 'email_service': None, 'sid_token': None, 'dropmail_session_id': None, 'dropmail_token': None}
    
    welcome_text = f"""**👋 Welcome {message.from_user.first_name}!**

🔐 **TempMail Bot** - Your Secure Temporary Email Service

This bot allows you to generate disposable email addresses to protect your privacy and avoid spam.

**🎯 Features:**
• Generate unlimited temporary emails
• Multiple email services (Guerrilla Mail & Mail.tm)
• Receive and read messages instantly
• Save emails for future reuse
• Manage multiple email addresses
• 100% anonymous and secure

**📌 Quick Start:**
Use the buttons below or try these commands:
/generate - Create a new email
/list - View your saved emails
/help - See all commands

**🛡️ Privacy:** Your emails are completely anonymous and self-destruct after a period of time."""
    
    await message.reply(welcome_text, reply_markup=buttons)

@app.on_message(filters.command('help'))
async def help_msg(client, message):
    help_text = """**📚 TempMail Bot - Command Guide**

**Basic Commands:**
/start - Start the bot and see main menu
/generate - Generate a new temporary email
/help - Show this help message

**Email Management:**
/list - List all your saved emails
/save <name> - Save current email with a custom name
/load <name> - Load a saved email
/delete <name> - Delete a saved email
/current - Show your current active email

**Button Actions:**
📧 Generate New - Create a fresh temporary email (choose service)
🔄 Refresh - Check for new messages
💾 Save Email - Save current email for reuse
📋 My Emails - View all saved emails
📖 View Message - Read full message content

**📬 Email Services:**
• **Guerrilla Mail** - Fast, one-time sessions (cannot be reloaded)
• **DropMail** - Fast AND reusable (best of both worlds!)
• **Mail.tm** - Secure, password-protected emails

**💡 Pro Tips:**
• Save emails you want to reuse later
• Use descriptive names when saving (e.g., "gaming", "shopping")
• Load saved emails to receive new verification codes
• Multiple users can use the bot simultaneously
• Try different services if one is blocked

**🔒 Privacy:** All emails are temporary and anonymous. No personal data is stored."""
    
    await message.reply(help_text)
@app.on_callback_query()
async def mailbox(client,message):
    response=message.data
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {'email': '', 'auth_token': None, 'idnum': None, 'saved_emails': {}, 'password': '', 'email_service': None, 'sid_token': None, 'dropmail_session_id': None, 'dropmail_token': None}
    
    if response=='generate':
        service_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton('⚡ Guerrilla Mail (Fast)', callback_data='gen_guerrilla')],
            [InlineKeyboardButton('📬 DropMail (Reusable)', callback_data='gen_dropmail')],
            [InlineKeyboardButton('🔐 Mail.tm (Secure)', callback_data='gen_mailtm')],
            [InlineKeyboardButton('❌ Cancel', callback_data='close')]
        ])
        await message.edit_message_text('**📧 Choose Email Service:**\n\n⚡ **Guerrilla Mail** - Fast, one-time sessions\n📬 **DropMail** - Fast AND reusable (best of both!)\n🔐 **Mail.tm** - Secure, password-protected\n\nSelect your preferred service:', reply_markup=service_buttons)
    
    elif response=='gen_guerrilla':
        try:
            await message.edit_message_text('🔄 Generating Guerrilla Mail address...')
            
            email_data = generate_guerrilla()
            if not email_data:
                await message.edit_message_text('❌ Unable to generate Guerrilla Mail. Please try Mail.tm instead.', reply_markup=buttons)
                return
            
            user_sessions[user_id]['email'] = email_data['email']
            user_sessions[user_id]['email_service'] = 'guerrilla'
            user_sessions[user_id]['sid_token'] = email_data['sid_token']
            user_sessions[user_id]['password'] = ''
            user_sessions[user_id]['auth_token'] = None
            user_sessions[user_id]['idnum'] = None
            
            await message.edit_message_text(
                f'**✅ Email Generated Successfully!**\n\n'
                f'📧 Your temporary email:\n`{email_data["email"]}`\n\n'
                f'🔧 Service: **Guerrilla Mail**\n'
                f'⚡ Fast delivery, no authentication required\n\n'
                f'💡 Use the buttons below to manage your inbox.',
                reply_markup=buttons
            )
            print(f"Generated Guerrilla Mail for user {user_id}: {email_data['email']}")
        except Exception as e:
            print(f"Error generating Guerrilla Mail: {e}")
            await message.edit_message_text('❌ Unable to generate email. Please try again.', reply_markup=buttons)
    
    elif response=='gen_dropmail':
        try:
            await message.edit_message_text('🔄 Generating DropMail address...')
            
            email_data = generate_dropmail()
            if not email_data:
                await message.edit_message_text('❌ Unable to generate DropMail. Please try another service.', reply_markup=buttons)
                return
            
            user_sessions[user_id]['email'] = email_data['email']
            user_sessions[user_id]['email_service'] = 'dropmail'
            user_sessions[user_id]['dropmail_session_id'] = email_data['session_id']
            user_sessions[user_id]['dropmail_token'] = email_data['token']
            user_sessions[user_id]['password'] = email_data['token']
            user_sessions[user_id]['auth_token'] = None
            user_sessions[user_id]['sid_token'] = None
            user_sessions[user_id]['idnum'] = None
            
            await message.edit_message_text(
                f'**✅ Email Generated Successfully!**\n\n'
                f'📧 Your temporary email:\n`{email_data["email"]}`\n\n'
                f'🔧 Service: **DropMail**\n'
                f'📬 Fast AND reusable - best of both worlds!\n'
                f'⏰ Auto-extends when you check messages\n\n'
                f'💡 Use the buttons below to manage your inbox.',
                reply_markup=buttons
            )
            print(f"Generated DropMail for user {user_id}: {email_data['email']}")
        except Exception as e:
            print(f"Error generating DropMail: {e}")
            await message.edit_message_text('❌ Unable to generate email. Please try again.', reply_markup=buttons)
    
    elif response=='gen_mailtm':
       try:
           import random
           import string
           
           await message.edit_message_text('🔄 Generating Mail.tm address...')
           
           domains_resp = re.get("https://api.mail.tm/domains", timeout=10)
           if domains_resp.status_code != 200:
               await message.edit_message_text('❌ Mail.tm service unavailable. Try Guerrilla Mail instead.', reply_markup=buttons)
               return
           
           domains = domains_resp.json()['hydra:member']
           if not domains:
               await message.edit_message_text('❌ No Mail.tm domains available.', reply_markup=buttons)
               return
           
           domain = domains[0]['domain']
           username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
           email = f"{username}@{domain}"
           password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
           
           account_data = {
               'address': email,
               'password': password
           }
           account_resp = re.post("https://api.mail.tm/accounts", json=account_data, timeout=10)
           
           if account_resp.status_code != 201:
               await message.edit_message_text('❌ Unable to create Mail.tm account. Try Guerrilla Mail instead.', reply_markup=buttons)
               return
           
           token_data = {
               'address': email,
               'password': password
           }
           token_resp = re.post("https://api.mail.tm/token", json=token_data, timeout=10)
           
           if token_resp.status_code == 200:
               user_sessions[user_id]['email'] = email
               user_sessions[user_id]['auth_token'] = token_resp.json()['token']
               user_sessions[user_id]['password'] = password
               user_sessions[user_id]['email_service'] = 'mailtm'
               user_sessions[user_id]['login'] = None
               user_sessions[user_id]['domain'] = None
               user_sessions[user_id]['idnum'] = None
               await message.edit_message_text(
                   f'**✅ Email Generated Successfully!**\n\n'
                   f'📧 Your temporary email:\n`{email}`\n\n'
                   f'🔧 Service: **Mail.tm**\n'
                   f'🔐 Secure and password-protected\n\n'
                   f'💡 Use the buttons below to manage your inbox.',
                   reply_markup=buttons
               )
               print(f"Generated Mail.tm email for user {user_id}: {email}")
           else:
               await message.edit_message_text('❌ Authentication failed. Try Guerrilla Mail instead.', reply_markup=buttons)
               
       except Exception as e:
           print(f"Error generating Mail.tm email: {e}")
           await message.edit_message_text('❌ Unable to generate Mail.tm email. Try Guerrilla Mail instead.', reply_markup=buttons)
    elif response=='refresh':
        session = user_sessions[user_id]
        print(f"Refreshing for user {user_id}, email: {session['email']}, service: {session.get('email_service')}")
        try:
            if not session['email']:
                await message.edit_message_text('Generate an email first',reply_markup=buttons)
                return
            
            service = session.get('email_service', 'mailtm')
            
            if service == 'guerrilla':
                if not session.get('sid_token'):
                    await message.answer('Email session expired. Please generate a new email.', show_alert=True)
                    return
                
                messages_data = check_guerrilla_messages(session['sid_token'])
                
                if not messages_data:
                    await message.answer(f'No messages were received..\nin your Mailbox {session["email"]}')
                    return
                
                latest_msg = messages_data[0]
                user_sessions[user_id]['idnum'] = latest_msg['mail_id']
                from_msg = latest_msg.get('mail_from', 'Unknown')
                subject = latest_msg.get('mail_subject', 'No Subject')
                refreshrply = 'You have a message from '+from_msg+'\n\nSubject : '+subject
                await message.edit_message_text(refreshrply, reply_markup=msg_buttons)
                
            elif service == 'dropmail':
                if not session.get('dropmail_token') or not session.get('dropmail_session_id'):
                    await message.answer('Email session expired. Please generate a new email.', show_alert=True)
                    return
                
                messages_data = check_dropmail_messages(session['dropmail_token'], session['dropmail_session_id'])
                
                if not messages_data:
                    await message.answer(f'No messages were received..\nin your Mailbox {session["email"]}')
                    return
                
                latest_msg = messages_data[0]
                user_sessions[user_id]['idnum'] = latest_msg['id']
                from_msg = latest_msg.get('fromAddr', 'Unknown')
                subject = latest_msg.get('headerSubject', 'No Subject')
                refreshrply = 'You have a message from '+from_msg+'\n\nSubject : '+subject
                await message.edit_message_text(refreshrply, reply_markup=msg_buttons)
                
            else:
                if not session['auth_token']:
                    await message.answer('Email session expired. Please generate a new email.', show_alert=True)
                    return
                
                headers = {
                    'Authorization': f'Bearer {session["auth_token"]}'
                }
                messages_resp = re.get("https://api.mail.tm/messages", headers=headers, timeout=10)
                
                if messages_resp.status_code != 200:
                    await message.answer('Unable to check messages. Please try again.', show_alert=True)
                    return
                
                messages_data = messages_resp.json()['hydra:member']
                
                if not messages_data:
                    await message.answer(f'No messages were received..\nin your Mailbox {session["email"]}')
                    return
                
                latest_msg = messages_data[0]
                user_sessions[user_id]['idnum'] = latest_msg['id']
                from_msg = latest_msg['from']['address']
                subject = latest_msg['subject']
                refreshrply = 'You have a message from '+from_msg+'\n\nSubject : '+subject
                await message.edit_message_text(refreshrply, reply_markup=msg_buttons)
                
        except Exception as e:
            print(f"Error refreshing messages for user {user_id}: {e}")
            await message.answer(f'No messages were received..\nin your Mailbox {session["email"]}')
    elif response=='view_msg':
        session = user_sessions[user_id]
        if not session['idnum']:
            await message.answer('Please refresh to check for messages first!', show_alert=True)
            return
        
        try:
            service = session.get('email_service', 'mailtm')
            
            if service == 'guerrilla':
                msg = read_guerrilla_message(session['sid_token'], session['idnum'])
                
                if not msg:
                    await message.answer('Unable to load message. Please try again.', show_alert=True)
                    return
                
                print(msg)
                
                from_mail = msg.get('mail_from', 'Unknown')
                date = msg.get('mail_date', 'Unknown')
                subjectt = msg.get('mail_subject', 'No Subject')
                body = msg.get('mail_text', msg.get('mail_body', ''))[:500]
                
                mailbox_view = f"From: {from_mail}\nDate: {date}\nSubject: {subjectt}\n\nMessage:\n{body}"
                
                attachments = msg.get('att', [])
                if attachments and len(attachments) > 0:
                    attachment_list = '\n\nAttachments:\n' + '\n'.join([f"- {att.get('att_name', 'file')}" for att in attachments])
                    mailbox_view += attachment_list
                
                await message.edit_message_text(mailbox_view, reply_markup=buttons)
                
            elif service == 'dropmail':
                msg = read_dropmail_message(session['dropmail_token'], session['dropmail_session_id'], session['idnum'])
                
                if not msg:
                    await message.answer('Unable to load message. Please try again.', show_alert=True)
                    return
                
                print(msg)
                
                from_mail = msg.get('fromAddr', 'Unknown')
                subjectt = msg.get('headerSubject', 'No Subject')
                body = msg.get('text', msg.get('html', ''))[:500]
                
                mailbox_view = f"From: {from_mail}\nSubject: {subjectt}\n\nMessage:\n{body}"
                
                download_url = msg.get('downloadUrl')
                if download_url:
                    mailbox_view += f"\n\n📥 Download: {download_url}"
                
                await message.edit_message_text(mailbox_view, reply_markup=buttons)
                
            else:
                if not session['auth_token']:
                    await message.answer('Email session expired. Please generate a new email.', show_alert=True)
                    return
                
                headers = {
                    'Authorization': f'Bearer {session["auth_token"]}'
                }
                msg_resp = re.get(f"https://api.mail.tm/messages/{session['idnum']}", headers=headers, timeout=10)
                
                if msg_resp.status_code != 200:
                    await message.answer('Unable to load message. Please try again.', show_alert=True)
                    return
                
                msg = msg_resp.json()
                print(msg)
                
                from_mail = msg['from']['address'] if isinstance(msg['from'], dict) else msg['from']
                date = msg['createdAt']
                subjectt = msg['subject']
                body = msg['text'] if msg.get('text') else msg.get('html', '')[:500]
                
                mailbox_view = f"From: {from_mail}\nDate: {date}\nSubject: {subjectt}\n\nMessage:\n{body}"
                
                attachments = msg.get('attachments', [])
                if attachments and len(attachments) > 0:
                    attachment_list = '\n\nAttachments:\n' + '\n'.join([f"- {att['filename']}" for att in attachments])
                    mailbox_view += attachment_list
                
                await message.edit_message_text(mailbox_view, reply_markup=buttons)
            
        except Exception as e:
            print(f"Error viewing message: {e}")
            await message.answer('Unable to view message. Please try again.', show_alert=True)
    elif response=='save_email':
        session = user_sessions[user_id]
        if not session['email']:
            await message.answer('No active email to save! Generate an email first.', show_alert=True)
            return
        await message.answer('💾 Send the name to save this email with (e.g., "gaming", "shopping"):', show_alert=False)
        user_sessions[user_id]['waiting_for_save_name'] = True
    
    elif response=='list_emails':
        saved_emails = get_saved_emails(user_id)
        if not saved_emails:
            await message.answer('📋 You have no saved emails yet!\n\nGenerate an email and use the "Save Email" button to save it for future use.', show_alert=True)
            return
        
        email_list = "**📋 Your Saved Emails:**\n\n"
        for idx, email_data in enumerate(saved_emails, 1):
            service_info = get_service_info(email_data.get('email_service', 'mailtm'))
            email_list += f"{idx}. **{email_data['email_name']}** {service_info['icon']}\n   `{email_data['email_address']}`\n   Service: {service_info['name']}\n\n"
        
        email_list += "\n💡 **Commands:**\n"
        email_list += "• `/load <name>` - Load a saved email\n"
        email_list += "• `/delete <name>` - Delete a saved email"
        
        await message.edit_message_text(email_list, reply_markup=buttons)
    
    elif response=='close':
        await message.edit_message_text('✅ **Session Closed**\n\nUse /start to begin again.')

@app.on_message(filters.command('generate'))
async def generate_cmd(client, message):
    user_id = message.from_user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = {'email': '', 'auth_token': None, 'idnum': None, 'saved_emails': {}, 'password': '', 'email_service': None, 'sid_token': None, 'dropmail_session_id': None, 'dropmail_token': None}
    
    service_buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton('⚡ Guerrilla Mail (Fast)', callback_data='gen_guerrilla')],
        [InlineKeyboardButton('📬 DropMail (Reusable)', callback_data='gen_dropmail')],
        [InlineKeyboardButton('🔐 Mail.tm (Secure)', callback_data='gen_mailtm')],
        [InlineKeyboardButton('❌ Cancel', callback_data='close')]
    ])
    
    await message.reply('**📧 Choose Email Service:**\n\n⚡ **Guerrilla Mail** - Fast, one-time sessions\n📬 **DropMail** - Fast AND reusable (best of both!)\n🔐 **Mail.tm** - Secure, password-protected\n\nSelect your preferred service:', reply_markup=service_buttons)

@app.on_message(filters.command('list'))
async def list_cmd(client, message):
    user_id = message.from_user.id
    saved_emails = get_saved_emails(user_id)
    
    if not saved_emails:
        await message.reply('📋 **No Saved Emails**\n\nYou have no saved emails yet!\n\nGenerate an email and use `/save <name>` or the "Save Email" button to save it.')
        return
    
    email_list = "**📋 Your Saved Emails:**\n\n"
    for idx, email_data in enumerate(saved_emails, 1):
        service_icon = '⚡' if email_data.get('email_service') == 'guerrilla' else '🔐'
        service_name = 'Guerrilla Mail' if email_data.get('email_service') == 'guerrilla' else 'Mail.tm'
        email_list += f"{idx}. **{email_data['email_name']}** {service_icon}\n   `{email_data['email_address']}`\n   Service: {service_name}\n\n"
    
    email_list += "\n💡 **Available Commands:**\n"
    email_list += "• `/load <name>` - Load a saved email\n"
    email_list += "• `/delete <name>` - Delete a saved email\n"
    email_list += "• `/current` - Show current active email"
    
    await message.reply(email_list)

@app.on_message(filters.command('save'))
async def save_cmd(client, message):
    user_id = message.from_user.id
    if user_id not in user_sessions:
        await message.reply('❌ No active session. Use /generate to create an email first.')
        return
    
    session = user_sessions[user_id]
    if not session['email']:
        await message.reply('❌ No active email to save! Use /generate to create an email first.')
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply('⚠️ **Usage:** `/save <name>`\n\nExample: `/save gaming`')
        return
    
    name = parts[1].strip()
    if len(name) > 50:
        await message.reply('❌ Name too long! Please use a name under 50 characters.')
        return
    
    email_service = session.get('email_service', 'mailtm')
    service_info = get_service_info(email_service)
    service_name = service_info['name']
    
    session_id_to_save = session.get('dropmail_session_id') if email_service == 'dropmail' else None
    
    if save_email_to_db(user_id, name, session['email'], session.get('password', ''), email_service, session_id_to_save):
        await message.reply(f'✅ **Email Saved Successfully!**\n\n📧 Email: `{session["email"]}`\n🔧 Service: **{service_name}**\n💾 Saved as: **{name}**\n\nUse `/load {name}` to reuse this email anytime!')
    else:
        await message.reply('❌ Failed to save email. Please try again.')

@app.on_message(filters.command('load'))
async def load_cmd(client, message):
    user_id = message.from_user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = {'email': '', 'auth_token': None, 'idnum': None, 'saved_emails': {}, 'password': '', 'email_service': None, 'sid_token': None, 'dropmail_session_id': None, 'dropmail_token': None}
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply('⚠️ **Usage:** `/load <name>`\n\nExample: `/load gaming`\n\nUse `/list` to see your saved emails.')
        return
    
    name = parts[1].strip()
    email_data = load_email_from_db(user_id, name)
    
    if not email_data:
        await message.reply(f'❌ No saved email found with name "**{name}**".\n\nUse `/list` to see your saved emails.')
        return
    
    status_msg = await message.reply(f'🔄 Loading email **{name}**...')
    
    try:
        email_service = email_data.get('email_service', 'mailtm')
        service_info = get_service_info(email_service)
        service_name = service_info['name']
        
        if email_service == 'guerrilla':
            await status_msg.edit(f'⚠️ **Guerrilla Mail Cannot Be Reloaded**\n\n📧 Saved email: `{email_data["email_address"]}`\n\n❌ Guerrilla Mail sessions expire and cannot receive new messages after being saved.\n\n💡 Generate a fresh Guerrilla Mail address using `/generate` to receive new messages!')
        elif email_service == 'dropmail':
            if not email_data.get('session_id'):
                await status_msg.edit('❌ DropMail session data not found. Please generate a new email.')
                return
            
            user_sessions[user_id]['email'] = email_data['email_address']
            user_sessions[user_id]['email_service'] = 'dropmail'
            user_sessions[user_id]['dropmail_token'] = email_data['password']
            user_sessions[user_id]['dropmail_session_id'] = email_data['session_id']
            user_sessions[user_id]['password'] = email_data['password']
            user_sessions[user_id]['auth_token'] = None
            user_sessions[user_id]['sid_token'] = None
            user_sessions[user_id]['idnum'] = None
            await status_msg.edit(f'✅ **Email Loaded Successfully!**\n\n📧 Active email: `{email_data["email_address"]}`\n🔧 Service: **{service_name}**\n💾 Loaded from: **{name}**\n📬 DropMail sessions auto-extend when checked\n\n💡 Use the "Refresh" button to check for new messages!', reply_markup=buttons)
        else:
            token_data = {'address': email_data['email_address'], 'password': email_data['password']}
            token_resp = re.post("https://api.mail.tm/token", json=token_data, timeout=10)
            
            if token_resp.status_code == 200:
                user_sessions[user_id]['email'] = email_data['email_address']
                user_sessions[user_id]['auth_token'] = token_resp.json()['token']
                user_sessions[user_id]['password'] = email_data['password']
                user_sessions[user_id]['email_service'] = 'mailtm'
                user_sessions[user_id]['sid_token'] = None
                user_sessions[user_id]['dropmail_session_id'] = None
                user_sessions[user_id]['dropmail_token'] = None
                user_sessions[user_id]['idnum'] = None
                await status_msg.edit(f'✅ **Email Loaded Successfully!**\n\n📧 Active email: `{email_data["email_address"]}`\n🔧 Service: **{service_name}**\n💾 Loaded from: **{name}**\n\n💡 Use the "Refresh" button to check for new messages!', reply_markup=buttons)
            else:
                await status_msg.edit('❌ Failed to authenticate saved email. It may have expired.')
    except Exception as e:
        print(f"Error in /load: {e}")
        await status_msg.edit('❌ Unable to load email. Please try again.')

@app.on_message(filters.command('delete'))
async def delete_cmd(client, message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply('⚠️ **Usage:** `/delete <name>`\n\nExample: `/delete gaming`\n\nUse `/list` to see your saved emails.')
        return
    
    name = parts[1].strip()
    if delete_email_from_db(user_id, name):
        await message.reply(f'✅ **Email Deleted!**\n\nSaved email "**{name}**" has been removed.')
    else:
        await message.reply(f'❌ No saved email found with name "**{name}**".\n\nUse `/list` to see your saved emails.')

@app.on_message(filters.command('current'))
async def current_cmd(client, message):
    user_id = message.from_user.id
    if user_id not in user_sessions or not user_sessions[user_id]['email']:
        await message.reply('❌ **No Active Email**\n\nYou don\'t have an active email right now.\n\nUse `/generate` to create a new email or `/load <name>` to load a saved one.')
        return
    
    session = user_sessions[user_id]
    service = session.get('email_service', 'mailtm')
    service_info = get_service_info(service)
    service_name = service_info['name']
    service_icon = service_info['icon']
    
    await message.reply(f'**📧 Current Active Email:**\n\n`{session["email"]}`\n🔧 Service: **{service_name}** {service_icon}\n\n💡 Use `/save <name>` to save this email for future use.', reply_markup=buttons)

@app.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    if user_id in user_sessions and user_sessions[user_id].get('waiting_for_save_name'):
        session = user_sessions[user_id]
        name = message.text.strip()
        
        if len(name) > 50:
            await message.reply('❌ Name too long! Please use a name under 50 characters.')
            return
        
        email_service = session.get('email_service', 'mailtm')
        service_info = get_service_info(email_service)
        service_name = service_info['name']
        
        session_id_to_save = session.get('dropmail_session_id') if email_service == 'dropmail' else None
        
        if save_email_to_db(user_id, name, session['email'], session.get('password', ''), email_service, session_id_to_save):
            await message.reply(f'✅ **Email Saved Successfully!**\n\n📧 Email: `{session["email"]}`\n🔧 Service: **{service_name}**\n💾 Saved as: **{name}**\n\nUse `/load {name}` to reuse this email anytime!', reply_markup=buttons)
        else:
            await message.reply('❌ Failed to save email. Please try again.')
        
        user_sessions[user_id]['waiting_for_save_name'] = False

# Initialize database on startup
print("🔄 Initializing database...")
init_database()

app.run()

# Stay tuned for more : Instagram[@riz.4d]
