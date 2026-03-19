import { Injectable } from '@angular/core';

export interface SourceSnippet {
  source: string;
  content: string;
  score?: number;
}

@Injectable({ providedIn: 'root' })
export class RagService {
  private apiUrl = 'http://localhost:8000';

  async uploadFile(file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${this.apiUrl}/documents/upload`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) throw new Error('Upload failed');
    return response.json();
  }

  async chatStream(
    message: string, 
    sessionId: string, 
    onUpdate: (token: string) => void, 
    onSources: (sources: SourceSnippet[]) => void
  ): Promise<void> {
    const response = await fetch(`${this.apiUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: sessionId })
    });

    if (!response.body) return;

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = ''; // Accumulates partial chunks

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      
      buffer = lines.pop() || '';

      for (const line of lines) {
        const cleanLine = line.trim();
        if (!cleanLine.startsWith('data: ')) continue;

        const jsonStr = cleanLine.replace('data: ', '').trim();
        if (!jsonStr) continue;

        try {
          const parsed = JSON.parse(jsonStr);
          
          // 1. Handle Sources Metadata
          if (parsed.sources && Array.isArray(parsed.sources)) {
            onSources(parsed.sources);
          } 
          
          // 2. Handle Text Tokens
          if (parsed.text) {
            onUpdate(parsed.text);
          }

          // 3. Handle Completion if backend sends a 'done' flag
          if (parsed.done) {
            console.log('Stream finished');
          }
        } catch (e) {
          console.warn("Partial JSON encountered, waiting for next chunk...");
        }
      }
    }
  }
}