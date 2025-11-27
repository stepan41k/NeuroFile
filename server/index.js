// server.js
import express from 'express'
import pkg from 'pg'
import cors from 'cors'
import bcrypt from 'bcrypt'
import jwt from 'jsonwebtoken'
import multer from 'multer'
import fs from 'fs'
import path from 'path'
import fetch from 'node-fetch' // Если у тебя Node 18+ можно убрать и использовать global fetch
import { fileURLToPath } from 'url'

const { Pool } = pkg

// --- Конфигурация ---
const app = express()
const PORT = process.env.PORT || 3000
const SECRET_KEY = process.env.JWT_SECRET || 'neuro-secret-key'
const UPLOADS_PATH = process.env.UPLOADS_PATH || './uploads'
const AI_SERVICE_URL = process.env.AI_SERVICE_URL || 'http://ai-agent:3001/chat/answer'
// server.js
const AI_SERVICE_SAVE_URL = process.env.AI_SERVICE_SAVE_URL || 'http://ai_agent:3001/create_file'

// Пути
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// Создаем папку uploads
if (!fs.existsSync(UPLOADS_PATH)) fs.mkdirSync(UPLOADS_PATH, { recursive: true })

// Middleware
app.use(cors())
app.use(express.json())
app.use('/uploads', express.static(UPLOADS_PATH))

// --- Подключение к Postgres ---
const pool = new Pool({
  user: process.env.DB_USER || 'admin',
  host: process.env.DB_HOST || 'localhost',
  database: process.env.DB_NAME || 'neuro_db',
  password: process.env.DB_PASSWORD || 'rootpassword',
  port: process.env.DB_PORT || 5432,
})

// Функция инициализации таблиц (создаёт колонки files_used и attention если их нет)
const initDB = async () => {
  let retries = 5
  while (retries) {
    try {
      await pool.query('SELECT NOW()')
      console.log('Connected to PostgreSQL successfully')
      break
    } catch (err) {
      console.log(`Database not ready, retrying in 5s... (${retries} left)`)
      retries -= 1
      await new Promise(res => setTimeout(res, 5000))
    }
  }

  try {
    // 1. Таблица Users
    await pool.query(`
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
      );
    `)

    // 2. Таблица Files
    await pool.query(`
      CREATE TABLE IF NOT EXISTS files (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        filename TEXT NOT NULL,
        original_name TEXT NOT NULL,
        size INTEGER,
        path TEXT NOT NULL,
        type TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `)

    // 3. Таблица Chats
    await pool.query(`
      CREATE TABLE IF NOT EXISTS chats (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `)

    // 4. Таблица Messages с JSONB полями files_used и attention
    await pool.query(`
      CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        chat_id INTEGER REFERENCES chats(id) ON DELETE CASCADE,
        role TEXT,
        content TEXT,
        files_used JSONB DEFAULT '[]'::jsonb,
        attention JSONB DEFAULT '[]'::jsonb,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
    `)

    console.log('Tables initialized (Users, Files, Chats, Messages with files_used & attention)')
  } catch (err) {
    console.error('Error initializing tables:', err)
  }
}

// Запускаем инициализацию
initDB()

// --- Настройка Multer ---
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOADS_PATH),
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9)
    cb(null, uniqueSuffix + path.extname(file.originalname))
  },
})

const upload = multer({
  storage: storage,
  limits: { fileSize: 50 * 1024 * 1024 },
})

// --- Middleware Auth ---
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization']
  const token = authHeader && authHeader.split(' ')[1]
  if (!token) return res.sendStatus(401)

  jwt.verify(token, SECRET_KEY, (err, user) => {
    if (err) return res.sendStatus(403)
    req.user = user
    next()
  })
}

// --- API Роуты ---

// 1. Регистрация
app.post('/api/register', async (req, res) => {
  const { username, password } = req.body
  if (!username || !password) return res.status(400).json({ error: 'Заполните все поля' })
  if (password.length < 6) return res.status(400).json({ error: 'Пароль слишком короткий (минимум 6 символов)' })

  try {
    const hashedPassword = await bcrypt.hash(password, 10)
    await pool.query('INSERT INTO users (username, password) VALUES ($1, $2)', [username, hashedPassword])
    res.json({ message: 'Аккаунт успешно создан!' })
  } catch (err) {
    if (err.code === '23505') {
      return res.status(409).json({ error: 'Пользователь с таким именем уже существует' })
    }
    console.error('Ошибка регистрации:', err)
    res.status(500).json({ error: 'Внутренняя ошибка сервера' })
  }
})

// 2. Логин
app.post('/api/login', async (req, res) => {
  const { username, password } = req.body
  try {
    const result = await pool.query('SELECT * FROM users WHERE username = $1', [username])
    const user = result.rows[0]
    if (!user) return res.status(400).json({ error: 'User not found' })

    if (await bcrypt.compare(password, user.password)) {
      const token = jwt.sign({ id: user.id, username: user.username }, SECRET_KEY)
      res.json({ token, username: user.username })
    } else {
      res.status(403).json({ error: 'Invalid password' })
    }
  } catch (err) {
    console.error(err)
    res.status(500).send()
  }
})

app.get('/api/auth/verify', authenticateToken, (req, res) => {
  res.json({ status: 'valid', user: { id: req.user.id, username: req.user.username } })
})

// 3. Загрузка файла
// 3. Загрузка файла + отправка на AI Agent
app.post('/api/files', authenticateToken, (req, res) => {
    const uploadSingle = upload.single('file')
    uploadSingle(req, res, async err => {
        if (err) return res.status(400).json({ error: err.message })
        if (!req.file) return res.status(400).json({ error: 'No file uploaded' })

        const originalname = Buffer.from(req.file.originalname, 'latin1').toString('utf8')
        const { filename, size, path: filePath } = req.file
        const ext = path.extname(originalname).toLowerCase().replace('.', '')
        let type = ['doc', 'docx', 'pdf', 'rtf'].includes(ext) ? ext : 'unknown'

        try {
            const result = await pool.query(
                `INSERT INTO files (user_id, filename, original_name, size, path, type)
                 VALUES ($1, $2, $3, $4, $5, $6) RETURNING id`,
                [req.user.id, filename, originalname, size, filePath, type]
            )
            const newFileId = result.rows[0].id

            // --- Отправка файла на AI Agent ---
            try {
                const FormData = (await import('form-data')).default
                const fs = (await import('fs')).default
                const form = new FormData()
                form.append('file', fs.createReadStream(filePath), originalname)

                const aiResponse = await fetch(AI_SERVICE_SAVE_URL, {
                    method: 'POST',
                    body: form,
                })

                if (!aiResponse.ok) {
                    console.error('AI Agent upload failed:', await aiResponse.text())
                } else {
                    console.log('File successfully uploaded to AI Agent')
                }
            } catch (aiErr) {
                console.error('Error uploading file to AI Agent:', aiErr)
            }

            // --- Ответ клиенту ---
            res.json({ id: newFileId, name: originalname, size, type })
        } catch (dbErr) {
            console.error(dbErr)
            res.status(500).json({ error: 'Database error' })
        }
    })
})

// 4. Список файлов
app.get('/api/files', authenticateToken, async (req, res) => {
  try {
    const result = await pool.query('SELECT id, original_name as name, size, type FROM files WHERE user_id = $1 ORDER BY uploaded_at DESC', [req.user.id])
    res.json(result.rows)
  } catch (err) {
    console.error(err)
    res.status(500).send()
  }
})

// 5. Удаление файла
app.delete('/api/files/:id', authenticateToken, async (req, res) => {
  const fileId = req.params.id
  try {
    const fileRes = await pool.query('SELECT path FROM files WHERE id = $1 AND user_id = $2', [fileId, req.user.id])
    if (fileRes.rows.length === 0) return res.status(404).json({ error: 'File not found' })
    const filePath = fileRes.rows[0].path
    await pool.query('DELETE FROM files WHERE id = $1', [fileId])
    fs.unlink(filePath, err => { if (err) console.error('Error deleting physical file:', err) })
    res.json({ message: 'Deleted' })
  } catch (err) {
    console.error(err)
    res.status(500).send()
  }
})

// Переименование файла
app.put('/api/files/:id', authenticateToken, async (req, res) => {
  const { id } = req.params
  const { name } = req.body
  const userId = req.user.id
  if (!name || name.trim().length === 0) return res.status(400).json({ error: 'Имя файла не может быть пустым' })

  try {
    const result = await pool.query('UPDATE files SET original_name = $1 WHERE id = $2 AND user_id = $3', [name.trim(), id, userId])
    if (result.rowCount === 0) return res.status(404).json({ error: 'Файл не найден или нет прав доступа' })
    res.json({ message: 'Файл успешно переименован' })
  } catch (err) {
    console.error('Ошибка переименования:', err)
    res.status(500).json({ error: 'Ошибка сервера' })
  }
})

// --- CHAT / CHATS ENDPOINTS ---

// Создать чат
app.post('/api/chats', authenticateToken, async (req, res) => {
  const { title } = req.body
  const chatTitle = title || 'New Chat'
  try {
    const result = await pool.query('INSERT INTO chats (user_id, title) VALUES ($1, $2) RETURNING id, title', [req.user.id, chatTitle])
    res.json(result.rows[0])
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: 'Db error' })
  }
})

// Получить список чатов
app.get('/api/chats', authenticateToken, async (req, res) => {
  try {
    const query = `
      SELECT c.id, c.title, COALESCE(MAX(m.timestamp), c.created_at) as last_activity
      FROM chats c
      LEFT JOIN messages m ON c.id = m.chat_id
      WHERE c.user_id = $1
      GROUP BY c.id
      ORDER BY last_activity DESC
    `
    const result = await pool.query(query, [req.user.id])
    res.json(result.rows)
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: 'Db error' })
  }
})

// Получить сообщения чата (включая files_used и attention)
app.get('/api/chats/:id/messages', authenticateToken, async (req, res) => {
  const chatId = req.params.id
  try {
    const chatCheck = await pool.query('SELECT id FROM chats WHERE id = $1 AND user_id = $2', [chatId, req.user.id])
    if (chatCheck.rows.length === 0) return res.status(403).json({ error: 'Access denied' })

    const msgs = await pool.query(
      `SELECT role, content, files_used, attention, timestamp FROM messages WHERE chat_id = $1 ORDER BY timestamp ASC`, [chatId]
    )
    res.json(msgs.rows)
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: 'Db error' })
  }
})

// --- Основной исправленный роут: отправка сообщения в чат и сохранение files_used/attention ---
app.post('/api/chat/send', authenticateToken, async (req, res) => {
  const { chat_id, content, separate_conflicts } = req.body
  const userId = req.user.id

  if (!chat_id || !content) return res.status(400).json({ error: 'Missing chat_id or content' })

  try {
    // 1) Проверка прав на чат
    const chatCheck = await pool.query('SELECT id FROM chats WHERE id = $1 AND user_id = $2', [chat_id, userId])
    if (chatCheck.rows.length === 0) return res.status(403).json({ error: 'Access denied to chat' })

    // 2) Сохраняем сообщение пользователя
    await pool.query(
      `INSERT INTO messages (chat_id, role, content, files_used, attention) VALUES ($1, $2, $3, $4, $5)`,
      [chat_id, 'user', content, JSON.stringify([]), JSON.stringify([])]
    )

    // 3) Собираем историю для AI: берем role, content, files_used, attention
    const historyRes = await pool.query(
      `SELECT role, content, files_used, attention FROM messages WHERE chat_id = $1 ORDER BY timestamp ASC`,
      [chat_id]
    )
    const rawHistory = historyRes.rows

    // 4) Список файлов пользователя
    const filesRes = await pool.query('SELECT original_name FROM files WHERE user_id = $1', [userId])
    const filesList = filesRes.rows.map(f => f.original_name)

    // 5) Формируем system instruction
    let systemInstruction = 'You are a helpful assistant.'
    if (filesList.length > 0) {
      systemInstruction += ` You have access to the following files: ${filesList.join(', ')}. Use them to answer user questions.`
    }
    if (separate_conflicts) {
      systemInstruction += ` IMPORTANT: The user wants a detailed conflict analysis. If you find contradictions between files, use the "attention" field in your response to list the conflicting file name pairs.`
    }

    const systemMessage = { role: 'system', message: systemInstruction }

    // 6) Форматируем историю в формат API (assistant/user)
    const formattedHistory = rawHistory.map(m => {
      const role = m.role === 'ai' ? 'assistant' : m.role // if role stored 'ai' -> assistant; 'user' stays user
      return {
        role,
        message: m.content,
        files_used: m.files_used || [],
        attention: m.attention || []
      }
    })

    // Собираем payload для внешнего AI сервиса
    const chatPayload = [systemMessage, ...formattedHistory]

    // 7) Отправляем в AI
    let aiText = ''
    let savedFilesUsed = []
    let savedAttention = []

    try {
      const aiResponse = await fetch(AI_SERVICE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          separate_conflicts: !!separate_conflicts,
          chat: chatPayload
        }),
      })

      if (!aiResponse.ok) {
        const errText = await aiResponse.text()
        throw new Error(`AI Service error: ${aiResponse.status} - ${errText}`)
      }

      const aiData = await aiResponse.json()

      // Ожидаем структуру { chat: [ { role: "assistant", message: "...", files_used: [...], attention: [...] }, ... ] }
      if (aiData && Array.isArray(aiData.chat) && aiData.chat.length > 0) {
        // Сохраним все assistant-сообщения, но вернём последнее в ответе
        for (const msgObj of aiData.chat) {
          if (!msgObj || msgObj.role !== 'assistant') continue
          const text = msgObj.message || ''
          const fu = msgObj.files_used && Array.isArray(msgObj.files_used) ? msgObj.files_used : []
          const at = msgObj.attention && Array.isArray(msgObj.attention) ? msgObj.attention : []

          // Сохраняем в БД как отдельное сообщение
          await pool.query(
            `INSERT INTO messages (chat_id, role, content, files_used, attention) VALUES ($1, $2, $3, $4, $5)`,
            [chat_id, 'ai', text, JSON.stringify(fu), JSON.stringify(at)]
          )

          // Для выдачи клиенту оставим последнее ассистентское сообщение и его метаданные
          aiText = text
          savedFilesUsed = fu
          savedAttention = at
        }
      } else {
        // Если структура другая или пустая —fallback: возьмём сырый ответ
        aiText = 'Error: Empty or invalid response structure from AI agent.'
      }
    } catch (aiErr) {
      console.error('AI Connection Error:', aiErr)
      aiText = 'Error: Could not connect to AI Agent. Please try again later.'
    }

    // 8) Возвращаем ответ фронтенду
    res.json({ role: 'ai', content: aiText, files_used: savedFilesUsed, attention: savedAttention })
  } catch (err) {
    console.error('Chat Endpoint Error:', err)
    res.status(500).json({ error: 'Internal Server Error' })
  }
})

// Запуск
const server = app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`)
})

server.setTimeout(300000)