import { Component, signal, viewChild, ElementRef, effect, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { RagService, SourceSnippet } from './services/rag.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  private ragService = inject(RagService) as any;

  scrollContainer = viewChild<ElementRef>('scrollContainer');

  userInput = signal('');
  messages = signal<ChatMessage[]>([]);
  activeSources = signal<SourceSnippet[]>([]);
  isThinking = signal(false);
  isUploading = signal(false);
  
  private sessionId = crypto.randomUUID();
  private apiUrl = 'http://localhost:8000';

  constructor() {
    // Effect to handle auto-scrolling when messages change
    effect(() => {
      this.messages();
      const container = this.scrollContainer();
      if (container) {
        setTimeout(() => {
          container.nativeElement.scrollTop = container.nativeElement.scrollHeight;
        }, 50);
      }
    });
  }

  async onFileUpload(event: Event) {
    const element = event.target as HTMLInputElement;
    const file = element.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    this.isUploading.set(true);
    try {
      const response = await fetch(`${this.apiUrl}/documents/upload`, { 
        method: 'POST', 
        body: formData 
      });
      if (response.ok) alert('Document Indexed Successfully');
    } catch (err) {
      console.error('Upload failed', err);
    } finally {
      this.isUploading.set(false);
      element.value = '';
    }
  }

  async sendMessage() {
    const query = this.userInput().trim();
    if (!query || this.isThinking()) return;

    // Reset UI state for new message
    this.userInput.set('');
    this.isThinking.set(true);
    this.activeSources.set([]);

    // Add User message and placeholder for Assistant
    this.messages.update((m) => [...m, { role: 'user', content: query }]);
    this.messages.update((m) => [...m, { role: 'assistant', content: '' }]);

    const lastIdx = this.messages().length - 1;

    try {
      const response = await fetch(`${this.apiUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query, session_id: this.sessionId }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let currentEvent = '';

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; 

        for (const line of lines) {
          const cleanLine = line.trim();
          if (!cleanLine) continue;

          if (cleanLine.startsWith('event: ')) {
            currentEvent = cleanLine.replace('event: ', '').trim();
            continue;
          }

          if (cleanLine.startsWith('data: ')) {
            const rawData = cleanLine.replace('data: ', '').trim();
            
            if (currentEvent === 'message') {
              this.isThinking.set(false);
              this.messages.update(m => {
                const updated = [...m];
                // Check if rawData is JSON or raw string
                try {
                   const p = JSON.parse(rawData);
                   updated[lastIdx].content += (p.text || p);
                } catch {
                   updated[lastIdx].content += rawData;
                }
                return updated;
              });
            } 
            else if (currentEvent === 'sources') {
              try {
                const parsed = JSON.parse(rawData);
                this.activeSources.set(parsed);
              } catch (e) {
                console.error("Source parse error", e);
              }
            }
            else if (currentEvent === 'status') {
              console.log("Status update:", rawData);
              // Keeps 'isThinking' true until 'message' event starts
            }
          }
        }
      }
    } catch (err) {
      console.error('Streaming error:', err);
    } finally {
      this.isThinking.set(false);
    }
  }
}