'use client'

import { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'danger' | 'ghost' | 'success' | 'warning'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
}

const variantClass: Record<Variant, string> = {
  primary: 'bg-violet-600 hover:bg-violet-700 text-white disabled:bg-violet-900 disabled:text-violet-400',
  danger:  'bg-red-600 hover:bg-red-700 text-white disabled:bg-red-900 disabled:text-red-400',
  ghost:   'bg-slate-800 hover:bg-slate-700 text-slate-200 disabled:text-slate-500',
  success: 'bg-emerald-600 hover:bg-emerald-700 text-white disabled:bg-emerald-900',
  warning: 'bg-amber-500 hover:bg-amber-600 text-slate-900 disabled:bg-amber-900',
}

const sizeClass = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}

export default function Button({
  variant = 'primary',
  size = 'md',
  loading,
  children,
  disabled,
  className = '',
  ...rest
}: Props) {
  return (
    <button
      disabled={disabled || loading}
      className={`rounded-lg font-medium transition-colors cursor-pointer disabled:cursor-not-allowed ${variantClass[variant]} ${sizeClass[size]} ${className}`}
      {...rest}
    >
      {loading ? <span className="opacity-70">Loading…</span> : children}
    </button>
  )
}
