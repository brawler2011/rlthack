import React, { useState } from 'react';
import { Search, Building2, ShieldCheck, Cpu } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'search' | 'lots' | 'batch'>('search');

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-sky-600 flex items-center justify-center text-white font-bold text-xl">
            Р
          </div>
          <div>
            <h1 className="font-semibold text-lg text-slate-900 leading-tight">
              Росэлторг • АИС ГЗ СПб
            </h1>
            <p className="text-xs text-slate-500">
              Интеллектуальный подбор поставщиков и производителей (XAI)
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex space-x-2">
          <button
            onClick={() => setActiveTab('search')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
              activeTab === 'search'
                ? 'bg-sky-50 text-sky-700'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Подбор поставщиков
          </button>
          <button
            onClick={() => setActiveTab('lots')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
              activeTab === 'lots'
                ? 'bg-sky-50 text-sky-700'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Каталог извещений
          </button>
          <button
            onClick={() => setActiveTab('batch')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
              activeTab === 'batch'
                ? 'bg-sky-50 text-sky-700'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Фоновый робот (Batch)
          </button>
        </nav>

        {/* Engine Status */}
        <div className="flex items-center gap-2 text-xs bg-slate-100 text-slate-700 px-3 py-1.5 rounded-full border border-slate-200">
          <Cpu className="w-3.5 h-3.5 text-emerald-600" />
          <span>DuckDB + CatBoost Ranker • Local ML</span>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <h2 className="text-base font-semibold text-slate-800 mb-2">
            Параметры закупки
          </h2>
          <p className="text-sm text-slate-500 mb-4">
            Выберите извещение из базы АИС ГЗ или введите параметры нового лота для запуска ML-ранжирования.
          </p>
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
              <input
                type="text"
                placeholder="Поиск по предмету закупки или коду ОКПД2..."
                className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
            <button className="bg-sky-600 hover:bg-sky-700 text-white px-5 py-2 rounded-lg text-sm font-medium transition">
              Найти поставщиков
            </button>
          </div>
        </div>

        {/* Placeholder for Results / Table */}
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500 shadow-sm">
          <Building2 className="w-10 h-10 mx-auto text-slate-300 mb-3" />
          <p className="text-sm font-medium text-slate-700">Готов к поиску и ранжированию</p>
          <p className="text-xs text-slate-400 mt-1">
            Ранжированный список с бейджами ролей (Производитель / Дистрибьютор) и SHAP-объяснениями
          </p>
        </div>
      </main>
    </div>
  );
}
