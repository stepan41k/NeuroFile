import express from 'express'
import pkg from 'pg' // Импорт pg
import cors from 'cors'
import bcrypt from 'bcrypt'
import jwt from 'jsonwebtoken'
import multer from 'multer'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const { Pool } = pkg

// --- Конфигурация ---
const app = express()
const PORT = process.env.PORT || 3000
const SECRET_KEY = process.env.JWT_SECRET || 'neuro-secret-key'
const UPLOADS_PATH = process.env.UPLOADS_PATH || './uploads'

// Пути
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// Создаем папку uploads
if (!fs.existsSync(UPLOADS_PATH))
	fs.mkdirSync(UPLOADS_PATH, { recursive: true })

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

// Функция инициализации таблиц
const initDB = async () => {
	let retries = 5
	while (retries) {
		try {
			await pool.query('SELECT NOW()') // Проверка связи
			console.log('Connected to PostgreSQL successfully')
			break
		} catch (err) {
			console.log(`Database not ready, retrying in 5s... (${retries} left)`)
			retries -= 1
			await new Promise(res => setTimeout(res, 5000))
		}
	}

	try {
		// Таблица пользователей
		await pool.query(`
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );
        `)

		// Таблица файлов
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
		console.log('Tables initialized')
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
const upload = multer({ storage })

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

	// 1. Простая валидация входных данных
	if (!username || !password) {
		return res.status(400).json({ error: 'Заполните все поля' })
	}
	if (password.length < 6) {
		return res
			.status(400)
			.json({ error: 'Пароль слишком короткий (минимум 6 символов)' })
	}

	try {
		const hashedPassword = await bcrypt.hash(password, 10)

		// 2. Пытаемся записать в БД
		await pool.query('INSERT INTO users (username, password) VALUES ($1, $2)', [
			username,
			hashedPassword,
		])

		res.json({ message: 'Аккаунт успешно создан!' })
	} catch (err) {
		// 3. ПРОВЕРКА НА ДУБЛИКАТ
		// Код '23505' в Postgres означает нарушение уникальности (duplicate key value violates unique constraint)
		if (err.code === '23505') {
			return res
				.status(409)
				.json({ error: 'Пользователь с таким именем уже существует' })
		}

		// Логируем другие ошибки в консоль сервера
		console.error('Ошибка регистрации:', err)
		res.status(500).json({ error: 'Внутренняя ошибка сервера' })
	}
})

// 2. Логин
app.post('/api/login', async (req, res) => {
	const { username, password } = req.body
	try {
		const result = await pool.query('SELECT * FROM users WHERE username = $1', [
			username,
		])
		const user = result.rows[0]

		if (!user) return res.status(400).json({ error: 'User not found' })

		if (await bcrypt.compare(password, user.password)) {
			const token = jwt.sign(
				{ id: user.id, username: user.username },
				SECRET_KEY
			)
			res.json({ token, username: user.username })
		} else {
			res.status(403).json({ error: 'Invalid password' })
		}
	} catch (err) {
		console.error(err)
		res.status(500).send()
	}
})

// 3. Загрузка файла
app.post(
	'/api/files',
	authenticateToken,
	upload.single('file'),
	async (req, res) => {
		if (!req.file) return res.status(400).json({ error: 'No file uploaded' })

		const { filename, size, path: filePath } = req.file

		// --- ИСПРАВЛЕНИЕ КОДИРОВКИ ---
		// Преобразуем "битую" строку Latin1 обратно в буфер, а затем читаем как UTF-8
		const originalname = Buffer.from(req.file.originalname, 'latin1').toString(
			'utf8'
		)
		// -----------------------------

		const ext = path.extname(originalname).toLowerCase().replace('.', '')
		const type = ['jpg', 'png', 'jpeg'].includes(ext) ? 'img' : ext

		try {
			const result = await pool.query(
				`INSERT INTO files (user_id, filename, original_name, size, path, type) 
             VALUES ($1, $2, $3, $4, $5, $6) 
             RETURNING id`,
				[req.user.id, filename, originalname, size, filePath, type]
			)

			const newFileId = result.rows[0].id
			// Возвращаем фронтенду уже правильное имя
			res.json({ id: newFileId, name: originalname, size, type })
		} catch (err) {
			console.error(err)
			res.status(500).json({ error: 'Database error' })
		}
	}
)

// 4. Список файлов
app.get('/api/files', authenticateToken, async (req, res) => {
	try {
		const result = await pool.query(
			'SELECT id, original_name as name, size, type FROM files WHERE user_id = $1 ORDER BY uploaded_at DESC',
			[req.user.id]
		)
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
		// Сначала получаем путь
		const fileRes = await pool.query(
			'SELECT path FROM files WHERE id = $1 AND user_id = $2',
			[fileId, req.user.id]
		)

		if (fileRes.rows.length === 0) {
			return res.status(404).json({ error: 'File not found' })
		}

		const filePath = fileRes.rows[0].path

		// Удаляем из БД
		await pool.query('DELETE FROM files WHERE id = $1', [fileId])

		// Удаляем физически с диска
		fs.unlink(filePath, err => {
			if (err) console.error('Error deleting physical file:', err)
		})

		res.json({ message: 'Deleted' })
	} catch (err) {
		console.error(err)
		res.status(500).send()
	}
})

app.put('/api/files/:id', authenticateToken, async (req, res) => {
	const { id } = req.params
	const { name } = req.body
	const userId = req.user.id

	// Валидация
	if (!name || name.trim().length === 0) {
		return res.status(400).json({ error: 'Имя файла не может быть пустым' })
	}

	try {
		const result = await pool.query(
			'UPDATE files SET original_name = $1 WHERE id = $2 AND user_id = $3',
			[name.trim(), id, userId]
		)

		if (result.rowCount === 0) {
			return res
				.status(404)
				.json({ error: 'Файл не найден или нет прав доступа' })
		}

		res.json({ message: 'Файл успешно переименован' })
	} catch (err) {
		console.error('Ошибка переименования:', err)
		res.status(500).json({ error: 'Ошибка сервера' })
	}
})

app.post('/api/register', async (req, res) => {
	const { username, password } = req.body

	// Серверная валидация
	if (!username || !password) {
		return res.status(400).json({ error: 'Все поля обязательны' })
	}
	if (password.length < 6) {
		return res
			.status(400)
			.json({ error: 'Пароль должен быть не менее 6 символов' })
	}

	try {
		const hashedPassword = await bcrypt.hash(password, 10)

		await pool.query('INSERT INTO users (username, password) VALUES ($1, $2)', [
			username,
			hashedPassword,
		])

		res.json({ message: 'Аккаунт успешно создан! Теперь войдите.' })
	} catch (err) {
		if (err.code === '23505') {
			// Ошибка уникальности Postgres
			return res
				.status(400)
				.json({ error: 'Такой пользователь уже существует' })
		}
		console.error(err)
		res.status(500).json({ error: 'Ошибка сервера' })
	}
})

// Запуск
app.listen(PORT, () => {
	console.log(`Server running on port ${PORT}`)
})
