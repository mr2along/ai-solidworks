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
  const [generating, setGenerating] = useState(false);
  const [success, setSuccess] = useState("");

  async function analyze() {
    setLoading(true);
    setError("");
    setSuccess("");
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

  async function generate() {
    setGenerating(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description, part_name: partName })
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        throw new Error(detail || "Không thể tạo file CAD.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${partName}-cad-files.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setSuccess("Đã tạo và tải gói CAD. Kiểm tra thư mục Downloads.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi khi tạo file CAD.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <main className="page">
      <header className="header">
        <div className="logo">CAD</div>
        <div><h1>AI CAD Generator</h1><p>Text-to-CAD · FreeCAD headless · Hugging Face Space</p></div>
        <span className="pill">MVP</span>
      </header>

      <section className="panel">
        <h2>Mô tả chi tiết cơ khí</h2>
        <p className="muted">Bản MVP hỗ trợ tấm chữ nhật có 4 lỗ xuyên. Ghi kích thước bằng mm và khoảng cách từ tâm lỗ đến mép.</p>
        <label htmlFor="description">Yêu cầu thiết kế</label>
        <textarea id="description" value={description} onChange={e => setDescription(e.target.value)} rows={4} />
        <label htmlFor="partName">Tên chi tiết / file</label>
        <input id="partName" value={partName} onChange={e => setPartName(e.target.value)} maxLength={80} pattern="[A-Za-z0-9_-]+" />
        <div className="actions">
          <button onClick={analyze} disabled={loading || generating || description.trim().length < 5}>
            {loading ? "Đang phân tích…" : "1. Kiểm tra kích thước"}
          </button>
          <button className="secondary" onClick={generate} disabled={generating || loading || description.trim().length < 5}>
            {generating ? "Đang dựng mô hình…" : "2. Tạo và tải file CAD"}
          </button>
        </div>
        {error && <div className="error" role="alert">{error}</div>}
        {success && <div className="successMessage" role="status">{success}</div>}
      </section>

      {plan && <section className="panel">
        <div className="resultHeading"><h2>Kế hoạch CAD</h2><span className="pill success">Đã kiểm tra schema</span></div>
        <p className="muted">Khi chọn tạo file, FreeCAD dựng khối và xuất các định dạng bên dưới. PDF là bản vẽ kích thước 2D sơ bộ, không phải bản vẽ được chứng nhận sản xuất.</p>
        <div className="summary">
          <div><span>Tên chi tiết</span><strong>{plan.part_name}</strong></div>
          <div><span>Đơn vị</span><strong>{plan.units}</strong></div>
          <div><span>Feature</span><strong>{plan.features.length}</strong></div>
          <div><span>Đầu ra</span><strong>{plan.outputs.join(", ").toUpperCase()}</strong></div>
        </div>
        <pre>{JSON.stringify(plan, null, 2)}</pre>
      </section>}
      <footer>FreeCAD tạo mô hình trong Space. Bản hiện tại dùng bộ phân tích quy tắc, chưa phải AI tổng quát; chỉ hỗ trợ mẫu tấm 4 lỗ.</footer>
    </main>
  );
}
