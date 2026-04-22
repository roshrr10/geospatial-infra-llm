"use client";

import React from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Language } from '../utils/translations';
import { Globe } from 'lucide-react';

const LanguageToggle: React.FC = () => {
  const { language, setLanguage } = useLanguage();

  const languages: { code: Language; label: string }[] = [
    { code: 'en', label: 'EN' },
    { code: 'kh', label: 'KH' },
    { code: 'ga', label: 'GA' },
  ];

  return (
    <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl shadow-inner border border-slate-200/50">
      <div className="flex items-center gap-1.5 px-2 text-slate-400">
        <Globe size={12} className="opacity-70" />
      </div>
      {languages.map((lang) => (
        <button
          key={lang.code}
          onClick={() => setLanguage(lang.code)}
          className={`
            px-3 py-1.5 rounded-lg text-[10px] font-black tracking-widest transition-all duration-200
            ${language === lang.code 
              ? 'bg-white text-blue-600 shadow-sm scale-105' 
              : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50'
            }
          `}
        >
          {lang.label}
        </button>
      ))}
    </div>
  );
};

export default LanguageToggle;
