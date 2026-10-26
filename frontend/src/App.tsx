import { useState } from "react";

type Plan = {
  part_name: string;
  units: string;
  features: Array<Record<string, unknown>>;
  outputs: string[];
};

export default function App() {
  const [description, setDescription] = useState(
    "Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm"
  );
  const [partName, setPartName] = useState("mounting_plate");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function analyze() {
    setLoading(true);
    setError("");
    setPlan(null);
    try {
      const response = await fetch("/api/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description, part_name: partName })
      });
      const body = await response.json();
      if (!response.ok) {
        const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        throw new Error(detail || "Không thể phân tích yêu cầu.");
      }
      setPlan(body.plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi kết nối backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <header className="header">
        <div className="logo">CAD</div>
        <div><h1>AI SolidWorks</h1><p>Text-to-CAD · MVP preview</p></div>
        <span className="pill">Chế độ xem kế hoạch</span>
      </header>

      <section className="panel">
        <h2>Mô tả chi tiết cơ khí</h2>
        <p className="muted">Nhập yêu cầu bằng tiếng Việt. MVP hiện hỗ trợ mẫu tấm chữ nhật có 4 lỗ.</p>
        <label htmlFor="description">Yêu cầu thiết kế</label>
        <textarea id="description" value={description} onChange={e => setDescription(e.target.value)} rows={4} />
        <label htmlFor="partName">Tên file / chi tiết</label>
        <input id="partName" value={partName} onChange={e => setPartName(e.target.value)} maxLength={80} />
        <button onClick={analyze} disabled={loading || description.trim().length < 5}>
          {loading ? "Đang phân tích…" : "Phân tích yêu cầu"}
        </button>
        {error && <div className="error" role="alert">{error}</div>}
      </section>

      {plan && <section className="panel">
        <div className="resultHeading"><h2>Kế hoạch CAD</h2><span className="pill success">Hợp lệ về schema</span></div>
        <p className="muted">Đây mới là kế hoạch dựng hình, chưa thực thi trên SOLIDWORKS.</p>
        <div className="summary">
          <div><span>Tên chi tiết</span><strong>{plan.part_name}</strong></div>
          <div><span>Đơn vị</span><strong>{plan.units}</strong></div>
          <div><span>Feature</span><strong>{plan.features.length}</strong></div>
          <div><span>Đầu ra</span><strong>{plan.outputs.join(", ").toUpperCase()}</strong></div>
        </div>
        <pre>{JSON.stringify(plan, null, 2)}</pre>
      </section>}
      <footer>AI SolidWorks MVP · Chưa kết nối thực thi CAD · Không gửi mã lệnh tùy ý đến máy Windows.</footer>
    </main>
  );
}