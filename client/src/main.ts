const API_URL = '/api'

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
        const profileBtn = document.getElementById('userProfileBtn')
		const profileMenu = document.getElementById('profileMenu')
		const confirmLogoutBtn = document.getElementById('confirmLogoutBtn')
		// const menuUsername = document.getElementById('menuUsername')

		// Клик по профилю -> Показать/Скрыть меню
		profileBtn?.addEventListener('click', e => {
			e.preventDefault()
			e.stopPropagation() // Чтобы клик не ушел на document

			// Обновляем имя в меню перед показом
			// if (menuUsername) {
			// 	menuUsername.innerText = localStorage.getItem('neuro_username') || 'User'
			// }

			profileMenu?.classList.toggle('d-none')
		})

		// 2. Логика выхода (нажатие на кнопку Log out в меню)
		confirmLogoutBtn?.addEventListener('click', () => {
			this.logout()
		})

		// 3. Закрытие меню при клике в любое другое место
		document.addEventListener('click', e => {
			if (profileMenu && !profileMenu.classList.contains('d-none')) {
				// Если клик был НЕ по меню и НЕ по кнопке профиля
				if (!profileMenu.contains(e.target as Node) && !profileBtn?.contains(e.target as Node)) {
					profileMenu.classList.add('d-none')
				}
			}
		})

		// Переключение на Регистрацию
		document.getElementById('toRegisterLink')?.addEventListener('click', e => {
			e.preventDefault()
			this.toggleForms(false)
		})

		// Переключение на Логин
		document.getElementById('toLoginLink')?.addEventListener('click', e => {
			e.preventDefault()
			this.toggleForms(true)
		})

		// Сабмит Логина
		this.loginForm.addEventListener('submit', async e => {
			e.preventDefault()
			await this.handleLogin()
		})

		// Сабмит Регистрации
		this.regForm.addEventListener('submit', async e => {
			e.preventDefault()
			await this.handleRegister()
		})

		// Logout кнопка (в сайдбаре)
		document.getElementById('logoutBtn')?.addEventListener('click', e => {
			e.preventDefault()
			this.logout()
		})
	}

	// --- Логика Регистрации ---
	private async handleRegister() {
		const username = (
			document.getElementById('regUser') as HTMLInputElement
		).value.trim()
		const password = (document.getElementById('regPass') as HTMLInputElement)
			.value
		const confirm = (
			document.getElementById('regPassConfirm') as HTMLInputElement
		).value

		// 1. Client-side Validation
		if (password.length < 6) {
			this.showMessage('Password must be at least 6 characters', 'error')
			return
		}
		if (password !== confirm) {
			this.showMessage('Passwords do not match', 'error')
			return
		}

		this.setLoading(true, 'regBtn')

		try {
			const res = await fetch(`${API_URL}/register`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, password }),
			})

			const data = await res.json()

			// Если сервер вернул ошибку (409 или 400), мы её ловим здесь
			if (!res.ok) {
				// data.error будет содержать "Пользователь с таким именем уже существует"
				throw new Error(data.error || 'Registration failed')
			}

			// Успех...
			this.showMessage(data.message, 'success')
			// ...
		} catch (err: any) {
			// Здесь ошибка показывается в красном окошке
			this.showMessage(err.message, 'error')
		} finally {
			this.setLoading(false, 'regBtn')
		}
	}

	// --- Логика Входа ---
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

			if (!res.ok) throw new Error(data.error || 'Login failed')

			// Сохраняем токен
			localStorage.setItem('neuro_token', data.token)
			localStorage.setItem('neuro_username', data.username)

			// Запускаем приложение
			this.onLoginSuccess(data.token, data.username)
			this.overlay.style.display = 'none'
		} catch (err: any) {
			this.showMessage(err.message, 'error')
		} finally {
			this.setLoading(false, 'loginBtn')
		}
	}

	// --- Утилиты ---

	private checkSession() {
		const token = localStorage.getItem('neuro_token')
		const user = localStorage.getItem('neuro_username')
		if (token && user) {
			this.onLoginSuccess(token, user)
			this.overlay.style.display = 'none'
		} else {
			this.overlay.style.display = 'flex'
		}
	}

	public logout() {
		localStorage.removeItem('neuro_token')
		localStorage.removeItem('neuro_username')
		location.reload()
	}

	private toggleForms(showLogin: boolean) {
		this.msgBox.className = 'd-none' // Скрыть сообщения
		if (showLogin) {
			this.loginForm.classList.remove('d-none')
			this.regForm.classList.add('d-none')
			document.getElementById('authSubtitle')!.innerText =
				'Login to your workspace'
		} else {
			this.loginForm.classList.add('d-none')
			this.regForm.classList.remove('d-none')
			document.getElementById('authSubtitle')!.innerText =
				'Create a new account'
		}
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

class NeuralInterface {
	private chatContainer: HTMLElement
	private userInput: HTMLTextAreaElement
	private sendBtn: HTMLButtonElement
	private fileInput: HTMLInputElement
	private fileListContainer: HTMLElement

	private searchInput: HTMLInputElement
	private filterTags: NodeListOf<HTMLElement>

	// Хранилище данных о файлах (State)
	private filesData: Array<{
		id: string
		name: string
		size: number
		type: string
	}> = []
	private currentFilter: string = 'all'

	private isGenerating: boolean = false

	private token: string = ''

	constructor(token: string, username: string) {
		this.token = token
		this.chatContainer = document.getElementById('chatContainer') as HTMLElement
		this.userInput = document.getElementById('userInput') as HTMLTextAreaElement
		this.sendBtn = document.getElementById('sendBtn') as HTMLButtonElement
		this.fileInput = document.getElementById('fileInput') as HTMLInputElement
		this.fileListContainer = document.getElementById(
			'fileListContainer'
		) as HTMLElement
		this.searchInput = document.getElementById(
			'fileSearchInput'
		) as HTMLInputElement
		this.filterTags = document.querySelectorAll('.filter-tag')
		const userDisplay = document.getElementById('usernameDisplay')
		if (userDisplay) userDisplay.innerText = username

		this.initAuth()
		this.initChat()
		this.initFiles()
	}

	// --- 1. Fake Auth Logic ---
	private initAuth() {
		const authOverlay = document.getElementById('authOverlay')
		const loginForm = document.getElementById('loginForm')

		loginForm?.addEventListener('submit', e => {
			e.preventDefault()
			// Mock Login Success
			if (authOverlay) {
				authOverlay.style.opacity = '0'
				setTimeout(() => authOverlay.remove(), 500)
			}
		})

		// Logout handler
		document.getElementById('logoutBtn')?.addEventListener('click', () => {
			location.reload()
		})
	}

	// --- 2. Chat Logic ---
	private initChat() {
		// Auto-resize textarea
		this.userInput.addEventListener('input', () => {
			this.userInput.style.height = 'auto'
			this.userInput.style.height =
				Math.min(this.userInput.scrollHeight, 150) + 'px'
		})

		// Send on Enter
		this.userInput.addEventListener('keydown', e => {
			if (e.key === 'Enter' && !e.shiftKey) {
				e.preventDefault()
				this.handleSend()
			}
		})

		this.sendBtn.addEventListener('click', () => this.handleSend())
	}

	private async handleSend() {
		const text = this.userInput.value.trim()
		if (!text || this.isGenerating) return

		// Hide welcome screen if exists
		const welcome = document.querySelector('.welcome-screen') as HTMLElement
		if (welcome) welcome.style.display = 'none'

		// 1. Show User Message
		this.appendMessage('You', text, 'user')
		this.userInput.value = ''
		this.userInput.style.height = 'auto'
		this.isGenerating = true

		// 2. Fake AI Thinking
		await this.simulateAIResponse()
	}

	private appendMessage(
		name: string,
		text: string,
		role: 'user' | 'ai'
	): HTMLElement {
		const wrapper = document.createElement('div')
		wrapper.className = `message-wrapper ${role}`

		let contentHtml = text.replace(/\n/g, '<br>')
		// Simple code block detector for demo
		if (contentHtml.includes('```')) {
			contentHtml = contentHtml.replace(
				/```([\s\S]*?)```/g,
				'<div class="code-block">$1</div>'
			)
		}

		const icon =
			role === 'ai' ? '<i class="bi bi-stars text-accent me-2"></i>' : ''

		wrapper.innerHTML = `
            <div class="message-role">${icon}${name}</div>
            <div class="message-content">${contentHtml}</div>
        `

		this.chatContainer.appendChild(wrapper)
		this.chatContainer.scrollTop = this.chatContainer.scrollHeight
		return wrapper.querySelector('.message-content') as HTMLElement
	}

	private async simulateAIResponse() {
		const responses = [
			"I've analyzed the uploaded files. Based on the context, here is the refactored code:\n```javascript\nconst optimization = true;\n```",
			"That's an interesting question. In the current interface configuration, the right sidebar manages the retrieval context.",
			'I am ready to process your request. Please specify the parameters.',
		]
		const reply = responses[Math.floor(Math.random() * responses.length)]

		// Create empty AI message
		const contentDiv = this.appendMessage('Neuro', '', 'ai')

		// Typewriter effect
		let i = 0
		const interval = setInterval(() => {
			contentDiv.innerHTML +=
				reply.charAt(i) === '\n' ? '<br>' : reply.charAt(i)
			this.chatContainer.scrollTop = this.chatContainer.scrollHeight
			i++
			if (i >= reply.length) {
				clearInterval(interval)
				this.isGenerating = false
				// Fix code block rendering after typing
				if (contentDiv.innerHTML.includes('```')) {
					contentDiv.innerHTML = contentDiv.innerHTML.replace(
						/```([\s\S]*?)```/g,
						'<div class="code-block">$1</div>'
					)
				}
			}
		}, 20)
	}

	private async loadFilesFromServer() {
		try {
			const token = localStorage.getItem('neuro_token')
			const res = await fetch(`${API_URL}/files`, {
				headers: { Authorization: `Bearer ${token}` },
			})
			const files = await res.json()

			this.filesData = [] // Очищаем старые/демо данные

			// Заполняем данными из БД
			files.forEach((f: any) => {
				this.addFileToState(f.id, f.name, f.size, f.type)
			})
		} catch (e) {
			console.error('Error loading files:', e)
		}
	}

	// --- 3. Files Logic (Updated with Renaming) ---
	private initFiles() {
		// Добавляем демо-данные

		this.loadFilesFromServer()

		// 1. Обработка загрузки файла
		this.fileInput.addEventListener('change', () => {
			if (this.fileInput.files && this.fileInput.files.length > 0) {
				const file = this.fileInput.files[0]
				// Вместо addFileToState вызываем uploadFile
				this.uploadFile(file)
			}
		})

		// 2. Обработка поиска (фильтрация при вводе)
		this.searchInput.addEventListener('input', () => {
			this.renderFiles()
		})

		// 3. Обработка клика по фильтрам
		this.filterTags.forEach(tag => {
			tag.addEventListener('click', () => {
				// Смена активного класса
				this.filterTags.forEach(t => t.classList.remove('active'))
				tag.classList.add('active')

				// Обновление фильтра
				this.currentFilter = tag.getAttribute('data-type') || 'all'
				this.renderFiles()
			})
		})
	}

	private addFileToState(
		id: string | number,
		name: string,
		size: number,
		type?: string
	) {
		// Если тип не передан, пытаемся определить по расширению
		if (!type) {
			const ext = name.split('.').pop()?.toLowerCase() || 'unknown'
			type = this.mapExtensionToType(ext)
		}

		const newFile = {
			id: id.toString(), // Приводим к строке для единообразия в JS
			name: name,
			size: size,
			type: type,
		}

		this.filesData.unshift(newFile)
		this.renderFiles()
	}

	private async uploadFile(file: File) {
		const formData = new FormData()
		formData.append('file', file)

		// Показываем какой-то индикатор загрузки (опционально)
		// Но пока просто заблокируем инпут
		this.fileInput.disabled = true

		try {
			const token = localStorage.getItem('neuro_token')
			const res = await fetch(`${API_URL}/files`, {
				method: 'POST',
				headers: {
					Authorization: `Bearer ${token}`,
					// Content-Type не нужен, браузер сам поставит multipart/form-data
				},
				body: formData,
			})

			if (!res.ok) throw new Error('Upload failed')

			const data = await res.json()

			// ВАЖНО: Добавляем файл в стейт, используя ID из базы данных (data.id)
			this.addFileToState(data.id, data.name, data.size, data.type)
		} catch (e) {
			console.error(e)
			alert('Ошибка загрузки файла')
		} finally {
			this.fileInput.value = '' // Сброс инпута
			this.fileInput.disabled = false
		}
	}

	private mapExtensionToType(ext: string): string {
		if (['jpg', 'jpeg', 'png', 'svg', 'webp'].includes(ext)) return 'img'
		if (['doc', 'docx'].includes(ext)) return 'docx'
		return ext // pdf, txt, etc.
	}

	private renderFiles() {
		this.fileListContainer.innerHTML = '' // Очищаем список
		const searchTerm = this.searchInput.value.toLowerCase()

		// Фильтрация
		const filteredFiles = this.filesData.filter(file => {
			const matchesSearch = file.name.toLowerCase().includes(searchTerm)
			const matchesType =
				this.currentFilter === 'all' || file.type === this.currentFilter
			return matchesSearch && matchesType
		})

		if (filteredFiles.length === 0) {
			this.fileListContainer.innerHTML = `
                <div class="text-muted text-center mt-3 small" style="font-size: 0.75rem;">
                    No files found
                </div>`
			return
		}

		// Отрисовка
		filteredFiles.forEach(file => {
			const domElement = this.createFileDOM(file)
			this.fileListContainer.appendChild(domElement)
		})
	}

	private createFileDOM(file: {
		id: string
		name: string
		size: number
	}): HTMLElement {
		const sizeStr =
			file.size < 1024 * 1024
				? (file.size / 1024).toFixed(1) + ' KB'
				: (file.size / (1024 * 1024)).toFixed(1) + ' MB'

		const div = document.createElement('div')
		div.className = 'file-item'
		div.innerHTML = `
            <div class="file-icon"><i class="bi bi-file-earmark-text"></i></div>
            <div class="file-info">
                <span class="file-name" title="${file.name}">${file.name}</span>
                <span class="file-size">${sizeStr}</span>
            </div>
            <div class="file-actions">
                <button class="action-btn edit" title="Rename"><i class="bi bi-pencil"></i></button>
                <button class="action-btn delete" title="Delete"><i class="bi bi-x"></i></button>
            </div>
        `

		// Логика удаления (удаляем из массива и перерисовываем)
		div.querySelector('.delete')?.addEventListener('click', () => {
			this.filesData = this.filesData.filter(f => f.id !== file.id)
			this.renderFiles()
		})

		// Логика переименования (из прошлого ответа)
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
				const currentName = nameSpan.innerText

				// Если имя не изменилось или пустое — просто отменяем
				if (!newName || newName === currentName) {
					input.remove()
					nameSpan.style.display = 'block'
					return
				}

				// Блокируем инпут пока идет запрос
				input.disabled = true

				try {
					// Отправляем запрос на сервер
					const token = localStorage.getItem('neuro_token')
					const res = await fetch(`${API_URL}/files/${file.id}`, {
						method: 'PUT',
						headers: {
							'Content-Type': 'application/json',
							Authorization: `Bearer ${token}`,
						},
						body: JSON.stringify({ name: newName }),
					})

					if (!res.ok) {
						const errData = await res.json()
						throw new Error(errData.error || 'Failed to rename')
					}

					// 1. Обновляем данные в локальном стейте (массиве)
					const targetFile = this.filesData.find(f => f.id === file.id)
					if (targetFile) targetFile.name = newName

					// 2. Обновляем UI
					nameSpan.innerText = newName
					nameSpan.title = newName
				} catch (err: any) {
					console.error(err)
					alert(`Ошибка: ${err.message}`)
					// Возвращаем старое имя при ошибке
					input.value = currentName
					nameSpan.innerText = currentName
				} finally {
					// Убираем инпут и показываем текст
					input.remove()
					nameSpan.style.display = 'block'
				}
			}

			input.addEventListener('keydown', e => {
				if (e.key === 'Enter') saveName()
				// По Esc отменяем редактирование
				if (e.key === 'Escape') {
					input.remove()
					nameSpan.style.display = 'block'
				}
			})

			// blur запускает сохранение, когда кликаем вне поля
			input.addEventListener('blur', () => saveName())

			input.addEventListener('keydown', e => {
				if (e.key === 'Enter') saveName()
			})
			input.addEventListener('blur', () => saveName())
		})

		return div
	}
}

// Start Application
// new NeuralInterface()

new AuthManager((token, username) => {
	new NeuralInterface(token, username)
})
