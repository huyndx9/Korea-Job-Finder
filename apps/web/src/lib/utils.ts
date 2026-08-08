import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Gộp class Tailwind, class sau ghi đè class trước khi trùng nhóm thuộc tính.
 * Cần thiết để component nhận prop `className` mà không bị xung đột thứ tự CSS.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
