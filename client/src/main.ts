// src/main.ts

class NeuralInterface {
    private chatContainer: HTMLElement;
    private userInput: HTMLTextAreaElement;
    private sendBtn: HTMLButtonElement;
    private welcomeScreen: HTMLElement | null;
    private isGenerating: boolean = false;

    constructor() {
        this.chatContainer = document.getElementById('chatContainer') as HTMLElement;
        this.userInput = document.getElementById('userInput') as HTMLTextAreaElement;
        this.sendBtn = document.getElementById('sendBtn') as HTMLButtonElement;
        this.welcomeScreen = document.querySelector('.welcome-screen') as HTMLElement;

        this.initEventListeners();
    }

    private initEventListeners(): void {
        this.sendBtn.addEventListener('click', () => this.handleUserMessage());

        this.userInput.addEventListener('keydown', (e: KeyboardEvent) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleUserMessage();
            }
        });

        this.userInput.addEventListener('input', () => {
            this.userInput.style.height = 'auto';
            this.userInput.style.height = Math.min(this.userInput.scrollHeight, 200) + 'px';
        });
    }

    private async handleUserMessage(): Promise<void> {
        const text = this.userInput.value.trim();
        if (!text || this.isGenerating) return;

        // Hide welcome screen smoothly
        if (this.welcomeScreen && this.welcomeScreen.style.display !== 'none') {
            this.welcomeScreen.style.opacity = '0';
            setTimeout(() => {
                if(this.welcomeScreen) this.welcomeScreen.style.display = 'none';
            }, 300);
        }

        this.appendMessage('You', text, 'user');
        this.userInput.value = '';
        this.userInput.style.height = 'auto';
        
        this.isGenerating = true;
        this.sendBtn.disabled = true;

        await this.simulateNetworkResponse();
    }

    private appendMessage(name: string, text: string, type: 'user' | 'ai'): HTMLElement {
        const msgWrapper = document.createElement('div');
        msgWrapper.className = `message-wrapper ${type}`;
        
        // Minimalist message structure: No bubbles, just clean text
        let formattedText = text.replace(/\n/g, '<br>');
        
        // Simple code block detection
        if (text.includes('```')) {
             formattedText = formattedText.replace(/```([\s\S]*?)```/g, '<div class="code-block">$1</div>');
        }

        const iconHtml = type === 'ai' ? '<i class="bi bi-stars text-warning me-2"></i>' : '';

        msgWrapper.innerHTML = `
            <div class="message-role">${iconHtml}${name}</div>
            <div class="message-content">${formattedText}</div>
        `;

        this.chatContainer.appendChild(msgWrapper);
        this.scrollToBottom();
        return msgWrapper.querySelector('.message-content') as HTMLElement;
    }

    private scrollToBottom(): void {
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
    }

    private async simulateNetworkResponse(): Promise<void> {
        await new Promise(resolve => setTimeout(resolve, 800));

        const responses = [
            "Here is a minimalist concept based on your request.\n\nI used a warm charcoal background (`#21201C`) to reduce eye strain, combined with a serif font for the headings to give it that 'Golden Hour' feel.",
            "To achieve this layout in CSS, I used Flexbox for the sidebar and a centered max-width container for the chat area. The input box has `position: relative` inside the bottom dock.",
            "Creating a `main.ts` file...\n```typescript\nconsole.log('Minimalism activated');\n```\nLet me know if you want to adjust the accent color."
        ];
        
        const randomResponse = responses[Math.floor(Math.random() * responses.length)];
        
        // Create empty message container for typing effect
        const contentDiv = this.appendMessage('Claude', '', 'ai');
        
        // Typing effect
        let i = 0;
        const interval = setInterval(() => {
            contentDiv.innerHTML += randomResponse.charAt(i) === '\n' ? '<br>' : randomResponse.charAt(i);
            i++;
            this.scrollToBottom();
            
            if (i > randomResponse.length - 1) {
                clearInterval(interval);
                this.isGenerating = false;
                this.sendBtn.disabled = false;
                
                // Post-process code blocks
                if(contentDiv.innerHTML.includes('```')) {
                   contentDiv.innerHTML = contentDiv.innerHTML.replace(/```([\s\S]*?)```/g, '<div class="code-block">$1</div>'); 
                }
            }
        }, 20);
    }
}

new NeuralInterface();