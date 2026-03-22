import { Component, signal, viewChild, ElementRef, effect, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { RagService, SourceSnippet } from './services/rag.service';
import { MarkdownPipe } from './pipes/markdown.pipe';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownPipe],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  private ragService = inject(RagService) as any;

  scrollContainer = viewChild<ElementRef>('scrollContainer');

  userInput = signal('');
  messages = signal<ChatMessage[]>([]);
  activeSources = signal<SourceSnippet[]>([]);
  isThinking = signal(false);
  isUploading = signal(false);
  uploadedDocs = signal<{ name: string }[]>([]);

  private sessionId = crypto.randomUUID();
  private apiUrl = 'http://localhost:8000';

  constructor() {
    this.loadDocs();

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
        body: formData,
      });
      if (response.ok) {
        this.loadDocs();
        alert('Document Indexed Successfully');
      }
    } catch (err) {
      console.error('Upload failed', err);
    } finally {
      this.isUploading.set(false);
      element.value = '';
    }
  }

  async loadDocs() {
    const docs = await this.ragService.getDocuments();
    this.uploadedDocs.set(docs);
  }

  async sendMessage() {
    const query = this.userInput().trim();
    if (!query || this.isThinking()) return;

    // Reset UI state for new message
    this.userInput.set('');
    this.isThinking.set(true);

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

            try {
              const parsedData = JSON.parse(rawData);

              if (currentEvent === 'message') {
                this.isThinking.set(false);
                this.messages.update((m) => {
                  const updated = [...m];
                  updated[lastIdx].content += parsedData.text || '';
                  return updated;
                });
              } else if (currentEvent === 'sources') {
                const sources = parsedData.sources || parsedData.results || [];
                console.log(sources);
                if (sources.length > 0) this.activeSources.set(sources);
              } else if (currentEvent === 'status') {
                console.log('Agent Status:', parsedData.status || parsedData);
              }
            } catch (e) {
              // If it's not JSON, handle as a fallback string
              if (currentEvent === 'message') {
                this.messages.update((m) => {
                  const updated = [...m];
                  updated[lastIdx].content += rawData;
                  return updated;
                });
              }
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