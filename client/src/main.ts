// URL для Nginx прокси (автоматически перенаправляет на сервер)
const API_URL = '/api'

// --- КЛАСС АВТОРИЗАЦИИ ---
class AuthManager {
	private overlay: HTMLElement
	private loginForm: HTMLFormElement
	private regForm: HTMLFormElement
	private msgBox: HTMLElement
	private onLoginSuccess: (token: string, username: string) => void

	constructor(onSuccess: (token: string, username: string) => void) {
		this.onLoginSuccess = onSuccess
		this.overlay = document.getElementById('authOverlay') as HTMLElement
		this.loginForm = document.getElementById('loginForm') as HTMLFormElement
		this.regForm = document.getElementById('registerForm') as HTMLFormElement
		this.msgBox = document.getElementById('authMessage') as HTMLElement

		this.initListeners()
		this.checkSession()
	}

	private initListeners() {
		document.getElementById('toRegisterLink')?.addEventListener('click', e => {
			e.preventDefault()
			this.toggleForms(false)
		})

		document.getElementById('toLoginLink')?.addEventListener('click', e => {
			e.preventDefault()
			this.toggleForms(true)
		})

		this.loginForm.addEventListener('submit', e => {
			e.preventDefault()
			this.handleLogin()
		})

		this.regForm.addEventListener('submit', e => {
			e.preventDefault()
			this.handleRegister()
		})

		// Меню профиля и выход
		const profileBtn = document.getElementById('userProfileBtn')
		const profileMenu = document.getElementById('profileMenu')
		const confirmLogoutBtn = document.getElementById('confirmLogoutBtn')

		profileBtn?.addEventListener('click', e => {
			e.preventDefault()
			e.stopPropagation()
			profileMenu?.classList.toggle('d-none')
		})

		confirmLogoutBtn?.addEventListener('click', () => this.logout())

		document.addEventListener('click', e => {
			if (profileMenu && !profileMenu.classList.contains('d-none')) {
				if (
					!profileMenu.contains(e.target as Node) &&
					!profileBtn?.contains(e.target as Node)
				) {
					profileMenu.classList.add('d-none')
				}
			}
		})
	}

	private async checkSession() {
		const token = localStorage.getItem('neuro_token')
		if (!token) {
			this.toggleOverlay(true)
			return
		}

		try {
			const res = await fetch(`${API_URL}/auth/verify`, {
				headers: { Authorization: `Bearer ${token}` },
			})
			if (!res.ok) throw new Error('Token invalid')

			const data = await res.json()
			this.onLoginSuccess(token, data.user.username)
			this.toggleOverlay(false)
		} catch (e) {
			this.logout(false)
		}
	}

	private async handleLogin() {
		const username = (
			document.getElementById('loginUser') as HTMLInputElement
		).value.trim()
		const password = (document.getElementById('loginPass') as HTMLInputElement)
			.value
		this.setLoading(true, 'loginBtn')

		try {
			const res = await fetch(`${API_URL}/login`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, password }),
			})
			const data = await res.json()
			if (!res.ok) throw new Error(data.error)

			localStorage.setItem('neuro_token', data.token)
			localStorage.setItem('neuro_username', data.username)
			this.onLoginSuccess(data.token, data.username)
			this.toggleOverlay(false)
		} catch (err: any) {
			this.showMessage(err.message, 'error')
		} finally {
			this.setLoading(false, 'loginBtn')
		}
	}

	private async handleRegister() {
		const usernameInput = document.getElementById('regUser') as HTMLInputElement
		const passwordInput = document.getElementById('regPass') as HTMLInputElement
		const confirmInput = document.getElementById(
			'regPassConfirm'
		) as HTMLInputElement

		const username = usernameInput.value.trim()
		const password = passwordInput.value
		const confirm = confirmInput.value

		if (password.length < 6)
			return this.showMessage('Min 6 chars password', 'error')
		if (password !== confirm)
			return this.showMessage('Passwords mismatch', 'error')

		this.setLoading(true, 'regBtn')
		try {
			const res = await fetch(`${API_URL}/register`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, password }),
			})
			const data = await res.json()
			if (!res.ok) throw new Error(data.error)

			this.showMessage('Account created! Redirecting...', 'success')
			setTimeout(() => {
				this.toggleForms(true)
				const loginUser = document.getElementById(
					'loginUser'
				) as HTMLInputElement
				if (loginUser) {
					loginUser.value = username
					loginUser.focus()
				}
				passwordInput.value = ''
				confirmInput.value = ''
				this.showMessage('Please log in', 'success')
			}, 300000)
		} catch (err: any) {
			this.showMessage(err.message, 'error')
		} finally {
			this.setLoading(false, 'regBtn')
		}
	}

	public logout(reload: boolean = true) {
		localStorage.removeItem('neuro_token')
		localStorage.removeItem('neuro_username')
		if (reload) location.reload()
		else {
			this.toggleForms(true)
			this.toggleOverlay(true)
		}
	}

	private toggleForms(showLogin: boolean) {
		this.msgBox.classList.add('d-none')
		if (showLogin) {
			this.loginForm.classList.remove('d-none')
			this.regForm.classList.add('d-none')
		} else {
			this.loginForm.classList.add('d-none')
			this.regForm.classList.remove('d-none')
		}
	}

	private toggleOverlay(show: boolean) {
		this.overlay.style.display = show ? 'flex' : 'none'
	}

	private showMessage(msg: string, type: 'error' | 'success') {
		this.msgBox.innerText = msg
		this.msgBox.className = `alert small p-2 mb-3 text-center ${
			type === 'error' ? 'alert-error' : 'alert-success'
		}`
		this.msgBox.classList.remove('d-none')
	}

	private setLoading(isLoading: boolean, btnId: string) {
		const btn = document.getElementById(btnId) as HTMLButtonElement
		const textSpan = btn.querySelector('.btn-text') as HTMLElement
		const spinner = btn.querySelector('.spinner-border') as HTMLElement
		btn.disabled = isLoading
		if (isLoading) {
			textSpan.classList.add('d-none')
			spinner.classList.remove('d-none')
		} else {
			textSpan.classList.remove('d-none')
			spinner.classList.add('d-none')
		}
	}
}

// --- ОСНОВНОЙ КЛАСС ИНТЕРФЕЙСА (ЧАТ + ФАЙЛЫ) ---
class NeuralInterface {
	private token: string
	private currentChatId: string | null = null
	private isGenerating: boolean = false

	// Элементы чата
	private chatContainer: HTMLElement
	private userInput: HTMLTextAreaElement
	private sendBtn: HTMLButtonElement
	private historyList: HTMLElement

	// Элементы файлов
	private searchInput: HTMLInputElement
	private fileInput: HTMLInputElement
	private fileListContainer: HTMLElement
	private filterTags: NodeListOf<HTMLElement>

	// Состояние файлов
	private filesData: Array<{
		id: string
		name: string
		size: number
		type: string
	}> = []
	private currentFilter: string = 'all'

	constructor(token: string, username: string) {
		this.token = token

		// UI Refs
		this.chatContainer = document.getElementById('chatContainer') as HTMLElement
		this.userInput = document.getElementById('userInput') as HTMLTextAreaElement
		this.sendBtn = document.getElementById('sendBtn') as HTMLButtonElement
		this.historyList = document.getElementById('historyList') as HTMLElement

		this.searchInput = document.getElementById(
			'fileSearchInput'
		) as HTMLInputElement
		this.fileInput = document.getElementById('fileInput') as HTMLInputElement
		this.fileListContainer = document.getElementById(
			'fileListContainer'
		) as HTMLElement
		this.filterTags = document.querySelectorAll('.filter-tag')

		const userDisplay = document.getElementById('usernameDisplay')
		if (userDisplay) userDisplay.innerText = username

		this.initListeners()
		this.initFilesLogic() // Инициализация файлов
		this.loadHistory() // Инициализация чатов
	}

	private initListeners() {
		document.querySelector('.new-chat-btn')?.addEventListener('click', e => {
			e.preventDefault()
			this.startNewChat()
		})

		this.sendBtn.addEventListener('click', () => this.handleSend())
		this.userInput.addEventListener('keydown', e => {
			if (e.key === 'Enter' && !e.shiftKey) {
				e.preventDefault()
				this.handleSend()
			}
		})

		this.userInput.addEventListener('input', () => {
			this.userInput.style.height = 'auto'
			this.userInput.style.height =
				Math.min(this.userInput.scrollHeight, 150) + 'px'
		})
	}

	// ==================
	// 1. ЛОГИКА ЧАТОВ
	// ==================

	private async loadHistory() {
		try {
			const res = await fetch(`${API_URL}/chats`, {
				headers: { Authorization: `Bearer ${this.token}` },
			})
			const chats = await res.json()
			this.renderHistorySidebar(chats)
		} catch (e) {
			console.error(e)
		}
	}

	private renderHistorySidebar(chats: any[]) {
		this.historyList.innerHTML = `
            <div class="small fw-bold px-3 mb-2 mt-3 text-uppercase" style="font-size: 0.75rem; letter-spacing: 0.5px;">
                <i class="bi bi-chat-square-text me-2"></i>Recent chats
            </div>
        `

		chats.forEach(chat => {
			const a = document.createElement('a')
			a.href = '#'
			a.className = 'nav-item'
			if (this.currentChatId == chat.id) a.classList.add('active')

			// Форматируем дату (используем поле last_activity от сервера)
			const dateStr = this.formatChatDate(chat.last_activity)

			// Новая структура HTML
			a.innerHTML = `
                <i class="bi bi-chat-left"></i>
                <div class="chat-info">
                    <span class="chat-title" title="${chat.title}">${chat.title}</span>
                    <span class="chat-date">${dateStr}</span>
                </div>
            `

			a.addEventListener('click', e => {
				e.preventDefault()
				this.loadChat(chat.id)
			})

			this.historyList.appendChild(a)
		})
	}

	private async loadChat(chatId: string) {
		this.currentChatId = chatId
		this.loadHistory() // Обновить active класс
		this.chatContainer.innerHTML = ''

		try {
			const res = await fetch(`${API_URL}/chats/${chatId}/messages`, {
				headers: { Authorization: `Bearer ${this.token}` },
			})
			const messages = await res.json()
            messages.forEach((msg: any) => {
                // Приводим files_used к массиву строк
                const files = (msg.files_used || []).map((f: any) =>
                    typeof f === 'string' ? f : f.name
                )

                // Передаем attention
                const attention = msg.attention || []

                this.appendMessage(
                    msg.role === 'user' ? 'You' : 'Neuro',
                    msg.content,
                    msg.role,
                    true,
                    files,
                    attention
                )
            }
        )
		} catch (e) {
			console.error(e)
		}
	}

	private startNewChat() {
		this.currentChatId = null
		this.chatContainer.innerHTML = ''
		const welcome = document.createElement('div')
		welcome.className = 'welcome-screen fade-in'
		welcome.innerHTML = `
            <div class="welcome-content">
                <h1 class="display-font">How can I help you today?</h1>
            </div>
        `
		this.chatContainer.appendChild(welcome)
		this.loadHistory() // Снять выделение
	}

	private formatChatDate(isoDate: string): string {
		const date = new Date(isoDate)
		const now = new Date()

		const isToday = date.toDateString() === now.toDateString()

		const yesterday = new Date(now)
		yesterday.setDate(now.getDate() - 1)
		const isYesterday = date.toDateString() === yesterday.toDateString()

		if (isToday) {
			// Если сегодня — показываем время (14:30)
			return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
		} else if (isYesterday) {
			return 'Yesterday'
		} else {
			// Иначе дату (25.11)
			return date.toLocaleDateString([], { day: '2-digit', month: '2-digit' })
		}
	}

	private async handleSend() {
		const text = this.userInput.value.trim()
		if (!text || this.isGenerating) return

		const conflictsToggle = document.getElementById(
			'conflictsToggle'
		) as HTMLInputElement
		const separateConflicts = conflictsToggle ? conflictsToggle.checked : false

		const welcome = document.querySelector('.welcome-screen')
		if (welcome) welcome.remove()

		this.appendMessage('You', text, 'user')
		this.userInput.value = ''
		this.userInput.style.height = 'auto'
		this.isGenerating = true

		try {
			if (!this.currentChatId) {
				// ... (код создания чата остается прежним) ...
				const title = text.slice(0, 30) + (text.length > 30 ? '...' : '')
				const createRes = await fetch(`${API_URL}/chats`, {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						Authorization: `Bearer ${this.token}`,
					},
					body: JSON.stringify({ title }),
				})
				const newChat = await createRes.json()
				this.currentChatId = newChat.id
				this.loadHistory()
			}

			// --- ОБНОВЛЕНИЕ: Анимация загрузки ---
			// Вставляем красивый HTML индикатор
			const loadingHTML = `
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            `
            const res = await fetch(`${API_URL}/chat/send`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${this.token}`,
				},
				body: JSON.stringify({
					chat_id: this.currentChatId,
					content: text,
					separate_conflicts: separateConflicts, // <-- ДОБАВИЛИ ПОЛЕ
				}),
			})

			if (!res.ok) throw new Error('Error')

			const data = await res.json()
            // Передаем false в format, чтобы не экранировать HTML
            const loadingMsg = this.appendMessage('Neuro', loadingHTML, 'ai', true, data.files_used || [])
            const contentDiv = loadingMsg.querySelector(
                '.message-content'
            ) as HTMLElement

			// Запускаем печать ответа (Typewriter)
			if (data.content) {
                await this.typeWriterEffect(contentDiv, data.content)
			} else if (data.error) {
				contentDiv.innerHTML = `❌ ${data.error}`
			} else {
				contentDiv.innerHTML = '❌ Unknown error'
			}
		} catch (e) {
			// Удаляем индикатор загрузки при ошибке, если он остался
			const loaders = document.querySelectorAll('.typing-indicator')
			loaders.forEach(el => el.remove())

			this.appendMessage('System', 'Error communicating with AI.', 'ai')
		} finally {
			this.isGenerating = false
		}
	}

    private appendMessage(
        name: string,
        text: string,
        role: string,
        shouldFormat: boolean = true,
        filesUsed: string[] = [],
        attention: number[][] = []
    ) {
        const wrapper = document.createElement('div')
        wrapper.className = `message-wrapper ${role}`

        const icon = role === 'ai' ? '<i class="bi bi-stars text-accent me-2"></i>' : ''
        const content = shouldFormat ? this.formatText(text) : text

        let filesHTML = ''
        if (filesUsed.length > 0) {
            filesHTML = `<div class="message-files"><strong>Files used:</strong> ${filesUsed
                .map(f => `<span class="file-tag">${f}</span>`)
                .join(', ')}</div>`
        }

        let attentionHTML = ''
        if (attention.length > 0) {
            attentionHTML = `<div class="message-attention"><strong>Attention:</strong> ${JSON.stringify(attention)}</div>`
        }

        wrapper.innerHTML = `
            <div class="message-role">${icon}${name}</div>
            <div class="message-content">${content}</div>
            ${filesHTML}
            ${attentionHTML}
        `

        this.chatContainer.appendChild(wrapper)
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight
        return wrapper
    } // <-- убедись, что эта скобка закрыта

	private formatText(text: string): string {
		// @ts-ignore
		if (typeof marked === 'undefined') return text

		// Настройка Marked (делаем один раз, но можно и тут)
		// @ts-ignore
		if (!this.markedConfigured) {
			// @ts-ignore
			const renderer = new marked.Renderer()

			// Переопределяем рендеринг блоков кода
			renderer.code = (code: string, language: string) => {
				// Подсветка синтаксиса
				// @ts-ignore
				const validLang = hljs.getLanguage(language) ? language : 'plaintext'
				// @ts-ignore
				const highlighted = hljs.highlight(code, { language: validLang }).value

				// Возвращаем HTML с кнопкой копирования
				// Мы кодируем сам код в атрибут data-code, чтобы потом его легко достать
				// encodeURIComponent нужен, чтобы кавычки не сломали HTML
				return `
                    <pre>
                        <button class="copy-btn" onclick="navigator.clipboard.writeText(decodeURIComponent('${encodeURIComponent(
													code
												)}')); this.innerText='Copied!'; setTimeout(()=>this.innerText='Copy', 300000);">
                            <i class="bi bi-clipboard"></i> Copy
                        </button>
                        <code class="hljs language-${validLang}">${highlighted}</code>
                    </pre>
                `
			}

			// @ts-ignore
			marked.use({ renderer })
			// @ts-ignore
			this.markedConfigured = true
		}

		// @ts-ignore
		return marked.parse(text)
	}

	// ==================
	// 2. ЛОГИКА ФАЙЛОВ
	// ==================

	private initFilesLogic() {
		this.loadFilesFromServer()

		// 1. Загрузка файла
		this.fileInput.addEventListener('change', () => {
			if (this.fileInput.files && this.fileInput.files.length > 0) {
				this.uploadFile(this.fileInput.files[0])
			}
		})

		// 2. ПОИСК: При вводе текста перерисовываем список
		this.searchInput.addEventListener('input', () => {
			this.renderFiles()
		})

		// 3. ФИЛЬТРЫ: При клике на тег перерисовываем список
		this.filterTags.forEach(tag => {
			tag.addEventListener('click', () => {
				this.filterTags.forEach(t => t.classList.remove('active'))
				tag.classList.add('active')

				this.currentFilter = tag.getAttribute('data-type') || 'all'
				this.renderFiles()
			})
		})
	}

	private async loadFilesFromServer() {
		try {
			const res = await fetch(`${API_URL}/files`, {
				headers: { Authorization: `Bearer ${this.token}` },
			})
			const files = await res.json()
			this.filesData = []
			files.forEach((f: any) => {
				this.addFileToState(f.id, f.name, f.size, f.type)
			})
		} catch (e) {
			console.error(e)
		}
	}

	private async uploadFile(file: File) {
		const formData = new FormData()
		formData.append('file', file)
		this.fileInput.disabled = true

		try {
			const res = await fetch(`${API_URL}/files`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${this.token}` },
				body: formData,
			})
			if (!res.ok) throw new Error('Upload failed')
			const data = await res.json()
			this.addFileToState(data.id, data.name, data.size, data.type)
		} catch (e) {
			alert('Error uploading file')
		} finally {
			this.fileInput.value = ''
			this.fileInput.disabled = false
		}
	}

	private addFileToState(
		id: string | number,
		name: string,
		size: number,
		type?: string
	) {
		if (!type) {
			const ext = name.split('.').pop()?.toLowerCase() || 'unknown'
			type = this.mapExtensionToType(ext)
		}
		this.filesData.unshift({ id: id.toString(), name, size, type })
		this.renderFiles()
	}

	private mapExtensionToType(ext: string): string {
		if (['doc', 'docx', 'rtf', 'pdf'].includes(ext)) return ext
		return 'unknown'
	}

	private async typeWriterEffect(element: HTMLElement, rawText: string) {
		// Превращаем Markdown в HTML сразу
		const html = this.formatText(rawText)

		element.innerHTML = '' // Очищаем индикатор загрузки

		let i = 0
		const speed = 10 // Скорость печати (чем меньше, тем быстрее)

		return new Promise<void>(resolve => {
			const interval = setInterval(() => {
				if (i >= html.length) {
					clearInterval(interval)
					resolve()
					return
				}

				const char = html.charAt(i)

				if (char === '<') {
					// Если это тег, ищем его конец и вставляем целиком
					const endIndex = html.indexOf('>', i)
					if (endIndex !== -1) {
						element.innerHTML += html.substring(i, endIndex + 1)
						i = endIndex + 1
					} else {
						element.innerHTML += char
						i++
					}
				} else if (char === '&') {
					// Если это спецсимвол (например &nbsp;), ищем конец
					const endIndex = html.indexOf(';', i)
					if (endIndex !== -1) {
						element.innerHTML += html.substring(i, endIndex + 1)
						i = endIndex + 1
					} else {
						element.innerHTML += char
						i++
					}
				} else {
					// Обычный текст
					element.innerHTML += char
					i++
				}

				this.chatContainer.scrollTop = this.chatContainer.scrollHeight
			}, speed)
		})
	}

	private renderFiles() {
		this.fileListContainer.innerHTML = ''

		// 1. Получаем текст поиска (в нижнем регистре для нечувствительности к регистру)
		const searchTerm = this.searchInput.value.toLowerCase().trim()

		// 2. Фильтруем массив данных
		const filtered = this.filesData.filter(f => {
			// Условие 1: Имя файла содержит текст поиска
			const matchSearch = f.name.toLowerCase().includes(searchTerm)

			// Условие 2: Тип файла совпадает с выбранным фильтром (или выбрано ALL)
			const matchType =
				this.currentFilter === 'all' || f.type === this.currentFilter

			// Файл должен соответствовать ОБОИМ условиям
			return matchSearch && matchType
		})

		// 3. Если ничего не найдено
		if (filtered.length === 0) {
			// Если поиск пустой, но файлов нет вообще
			if (this.filesData.length === 0) {
				this.fileListContainer.innerHTML = `<div class="text-center mt-3 small">No uploaded files</div>`
			} else {
				// Если файлы есть, но поиск не дал результатов
				this.fileListContainer.innerHTML = `<div class="text-center mt-3 small">No matches found</div>`
			}
			return
		}

		// 4. Отрисовка найденного
		filtered.forEach(file => {
			this.fileListContainer.appendChild(this.createFileDOM(file))
		})
	}

	private createFileDOM(file: {
		id: string
		name: string
		size: number
		type?: string
	}) {
		const sizeStr =
			file.size < 1024 * 1024
				? (file.size / 1024).toFixed(1) + ' KB'
				: (file.size / (1024 * 1024)).toFixed(1) + ' MB'

		let iconClass = 'bi-file-earmark'

		// Если тип пришел как "word" (от старых загрузок), пытаемся уточнить его по имени
		let type = file.type
		if (!type || type === 'word') {
			type = this.mapExtensionToType(
				file.name.split('.').pop()?.toLowerCase() || ''
			)
		}

		// Настройка иконок
		if (type === 'pdf') iconClass = 'bi-file-earmark-pdf text-light'
		// Для DOC и DOCX используем одну и ту же синюю иконку
		else if (type === 'doc' || type === 'docx')
			iconClass = 'bi-file-earmark-word text-light'
		else if (type === 'rtf') iconClass = 'bi-file-earmark-richtext text-light'

		const div = document.createElement('div')
		div.className = 'file-item'
		div.innerHTML = `
            <div class="file-icon"><i class="bi ${iconClass}"></i></div>
            <div class="file-info">
                <span class="file-name" title="${file.name}">${file.name}</span>
                <span class="file-size">${sizeStr}</span>
            </div>
            <div class="file-actions">
                <button class="action-btn edit"><i class="bi bi-pencil"></i></button>
                <button class="action-btn delete"><i class="bi bi-x"></i></button>
            </div>
        `

		// Удаление
		div.querySelector('.delete')?.addEventListener('click', async () => {
			if (!confirm('Delete file?')) return
			try {
				await fetch(`${API_URL}/files/${file.id}`, {
					method: 'DELETE',
					headers: { Authorization: `Bearer ${this.token}` },
				})
				this.filesData = this.filesData.filter(f => f.id !== file.id)
				this.renderFiles()
			} catch (e) {
				alert('Error deleting')
			}
		})

		// Переименование
		const editBtn = div.querySelector('.edit') as HTMLButtonElement
		const nameSpan = div.querySelector('.file-name') as HTMLElement
		const fileInfoDiv = div.querySelector('.file-info') as HTMLElement

		editBtn.addEventListener('click', () => {
			const currentName = nameSpan.innerText
			const input = document.createElement('input')
			input.type = 'text'
			input.value = currentName
			input.className = 'rename-input'

			nameSpan.style.display = 'none'
			fileInfoDiv.insertBefore(input, nameSpan)
			input.focus()

			const saveName = async () => {
				const newName = input.value.trim()
				if (!newName || newName === currentName) {
					input.remove()
					nameSpan.style.display = 'block'
					return
				}
				input.disabled = true
				try {
					const res = await fetch(`${API_URL}/files/${file.id}`, {
						method: 'PUT',
						headers: {
							'Content-Type': 'application/json',
							Authorization: `Bearer ${this.token}`,
						},
						body: JSON.stringify({ name: newName }),
					})
					if (!res.ok) throw new Error()

					const target = this.filesData.find(f => f.id === file.id)
					if (target) target.name = newName

					nameSpan.innerText = newName
					nameSpan.title = newName
				} catch (e) {
					alert('Error renaming')
					nameSpan.innerText = currentName
				} finally {
					input.remove()
					nameSpan.style.display = 'block'
				}
			}

			input.addEventListener('keydown', e => {
				if (e.key === 'Enter') saveName()
				if (e.key === 'Escape') {
					input.remove()
					nameSpan.style.display = 'block'
				}
			})
			input.addEventListener('blur', () => saveName())
		})

		return div
	}
}

// Запуск
new AuthManager((token, username) => {
	new NeuralInterface(token, username)
})
