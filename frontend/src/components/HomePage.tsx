import { ArrowUpRight, FileSpreadsheet, FileText } from "lucide-react";

export default function HomePage() {
  return (
    <main id="main" className="scenario-page home-page" aria-label="Выбор сценария подбора">
      <div className="scenario-grid">
        <a href="/single" className="scenario-card">
          <span className="scenario-icon">
            <FileText size={28} />
          </span>
          <span className="eyebrow">Одна закупка</span>
          <h2>Подбор одного лота</h2>
          <p>
            Выберите извещение из базы или задайте параметры закупки вручную. Уточните подбор с
            помощью фильтров.
          </p>
          <span className="scenario-action">
            Перейти к подбору <ArrowUpRight size={18} />
          </span>
        </a>
        <a href="/csv" className="scenario-card csv-scenario">
          <span className="scenario-icon">
            <FileSpreadsheet size={28} />
          </span>
          <span className="eyebrow">Несколько закупок</span>
          <h2>Подбор по CSV</h2>
          <p>
            Загрузите извещения и потоварку. Получите подбор для каждой закупки с причинами
            рекомендаций и подробностями компаний.
          </p>
          <span className="scenario-action">
            Загрузить файлы <ArrowUpRight size={18} />
          </span>
        </a>
      </div>
    </main>
  );
}
