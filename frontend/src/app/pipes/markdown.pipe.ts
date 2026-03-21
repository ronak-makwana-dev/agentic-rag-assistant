import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'markdown',
  standalone: true
})
export class MarkdownPipe implements PipeTransform {
  async transform(value: string): Promise<string> {
    if (!value) return '';
    console.log(value)
    let formatted = value
      .replace(/\*\*(.*?)\*\*/g, '<b style="color: #2563eb;">$1</b>')
      .replace(/^\* (.*)/gm, '<div style="margin-left: 10px;">• $1</div>')
      .replace(/\[Source: (.*?)\]/g, '<small style="display:block; margin-top:5px; color: #64748b; font-style: italic;">Source: $1</small>');
      
    formatted = formatted.replace(/\n/g, '<br>');
    return await formatted;
  }
}