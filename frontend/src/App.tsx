import { useState } from "react";

type Position = { x?: number; y?: number };
type Feature = {
  id: string;
  type: "extruded_plate" | "through_holes";
  length?: number | null;
  width?: number | null;
  thickness?: number | null;
  diameter?: number | null;
  positions?: Position[];
};
type Plan = {
  schema_version: string;
  part_name: string;
  units: string;
  backend: string;
  validation: "passed" | "pending_server_recheck";
  parameters: Record<string, number>;
  constraints: string[];
  assumptions: string[];
  warnings: string[];
  features: Feature[];
  outputs: string[];
};

function deriveParameters(features: Feature[]) {
  const result: Record<string, number> = {};
  const base = features[0];
  if (base?.length !== null && base?.length !== undefined) result.length_mm = base.length;
  if (base?.width !== null && base?.width !== undefined) result.width_mm = base.width;
  if (base?.thickness !== null && base?.thickness !== undefined) result.thickness_mm = base.thickness;
  const holes = features.find(feature => feature.type === "through_holes");
  if (holes?.diameter !== null && holes?.diameter !== undefined) result.hole_diameter_mm = holes.diameter;
  if (holes?.positions) {
    result.hole_count = holes.positions.length;
    holes.positions.forEach((position, index) => {
      if (position.x !== undefined) result[`hole_${index + 1}_x_mm`] = position.x;
      if (position.y !== undefined) result[`hole_${index + 1}_y_mm`] = position.y;
    });
  }
  return result;
}

const initialDescription = "Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm";

export default function App() {
  const [description, setDescription] = useState(initialDescription);
  const [partName, setPartName] = useState("mounting_plate");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [edited, setEdited] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [success, setSuccess] = useState("");

  function clearPreview() {
    setPlan(null);
    setEdited(false);
    setSuccess("");
  }

  function updateFeatureNumber(
    featureIndex: number,
    field: "length" | "width" | "thickness" | "diameter",
    rawValue: string
  ) {
    const value = rawValue === "" ? undefined : Number(rawValue);
    if (value !== undefined && !Number.isFinite(value)) return;
    setPlan(current => {
      if (!current) return current;
      const features = current.features.map((feature, index) =>
        index === featureIndex ? { ...feature, [field]: value } : feature
      );
      return { ...current, features, parameters: deriveParameters(features), constraints: [], validation: "pending_server_recheck" };
    });
    setEdited(true);
  }

  function updateHolePosition(featureIndex: number, holeIndex: number, axis: "x" | "y", rawValue: string) {
    const value = rawValue === "" ? undefined : Number(rawValue);
    if (value !== undefined && !Number.isFinite(value)) return;
    setPlan(current => {
      if (!current) return current;
      const features = current.features.map((feature, index) => {
        if (index !== featureIndex) return feature;
        return {
          ...feature,
          positions: feature.positions?.map((position, index) =>
            index === holeIndex ? { ...position, [axis]: value } : position
          )
        };
      });
      return { ...current, features, parameters: deriveParameters(features), constraints: [], validation: "pending_server_recheck" };
    });
    setEdited(true);
  }

  async function analyze() {
    setLoading(true);
    setError("");
    setSuccess("");
    setPlan(null);
    setEdited(false);
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
      setPlan(body.plan as Plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi kết nối backend.");
    } finally {
      setLoading(false);
    }
  }

  async function generate() {
    if (!plan) return;
    setGenerating(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // Send the exact plan shown for review. The server validates it again.
        body: JSON.stringify({ plan: { ...plan, validation: "passed" } })
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        throw new Error(detail || `Không thể tạo file CAD (HTTP ${response.status}).`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${plan.part_name}-cad-files.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setSuccess("Backend đã xác nhận tạo file; gói CAD đang được tải xuống.");
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
        <div><h1>AI CAD Agent</h1><p>Text-to-CAD · FreeCAD headless · Hugging Face Space</p></div>
        <span className="pill">MVP</span>
      </header>

      <section className="panel">
        <h2>Mô tả chi tiết cơ khí</h2>
        <p className="muted">Bản hiện tại hỗ trợ tấm chữ nhật có các lỗ xuyên. Hãy ghi rõ kích thước bằng mm và rà soát CAD Plan trước khi tạo.</p>
        <label htmlFor="description">Yêu cầu thiết kế</label>
        <textarea id="description" disabled={loading || generating} value={description} onChange={e => { setDescription(e.target.value); clearPreview(); }} rows={4} />
        <label htmlFor="partName">Tên chi tiết / file</label>
        <input id="partName" disabled={loading || generating} value={partName} onChange={e => { setPartName(e.target.value); clearPreview(); }} maxLength={80} pattern="[A-Za-z0-9_-]+" />
        <div className="actions">
          <button onClick={analyze} disabled={loading || generating || description.trim().length < 5}>
            {loading ? "Đang phân tích…" : "1. Tạo CAD Plan để xem trước"}
          </button>
          <button className="secondary" onClick={generate} disabled={!plan || generating || loading}>
            {generating ? "Đang dựng mô hình…" : "2. Xác nhận và tạo file CAD"}
          </button>
        </div>
        {error && <div className="error" role="alert">{error}</div>}
        {success && <div className="successMessage" role="status">{success}</div>}
      </section>

      {plan && <section className="panel">
        <div className="resultHeading">
          <h2>Kế hoạch CAD cần rà soát</h2>
          <span className="pill success">{edited ? "Sẽ xác thực lại khi tạo" : "Schema và ràng buộc hợp lệ"}</span>
        </div>
        <p className="muted">Chỉnh thông số bên dưới nếu cần. Khi xác nhận tạo, máy chủ sẽ xác thực lại toàn bộ kế hoạch trước khi gọi FreeCAD.</p>
        <div className="summary">
          <div><span>Tên chi tiết</span><strong>{plan.part_name}</strong></div>
          <div><span>Đơn vị</span><strong>{plan.units}</strong></div>
          <div><span>Backend</span><strong>{plan.backend}</strong></div>
          <div><span>Đầu ra</span><strong>{plan.outputs.join(", ").toUpperCase()}</strong></div>
        </div>
        {plan.features.map((feature, featureIndex) => feature.type === "extruded_plate" ? (
          <fieldset className="featureEditor" key={feature.id}>
            <legend>Feature {featureIndex + 1}: Tấm đùn</legend>
            {([ ["length", "Dài (mm)"], ["width", "Rộng (mm)"], ["thickness", "Dày (mm)"] ] as const).map(([key, label]) => (
              <label key={key}>{label}
                <input disabled={loading || generating} type="number" min="0" step="any" value={feature[key] ?? ""} onChange={e => updateFeatureNumber(featureIndex, key, e.target.value)} />
              </label>
            ))}
          </fieldset>
        ) : (
          <fieldset className="featureEditor" key={feature.id}>
            <legend>Feature {featureIndex + 1}: Lỗ xuyên</legend>
            <label>Đường kính (mm)
              <input disabled={loading || generating} type="number" min="0" step="any" value={feature.diameter ?? ""} onChange={e => updateFeatureNumber(featureIndex, "diameter", e.target.value)} />
            </label>
            <div className="holeGrid"><strong>Lỗ</strong><strong>Tâm X (mm)</strong><strong>Tâm Y (mm)</strong>
              {feature.positions?.map((position, holeIndex) => <div className="holeRow" key={holeIndex}>
                <span>{holeIndex + 1}</span>
                <input disabled={loading || generating} aria-label={`Lỗ ${holeIndex + 1}, tọa độ X`} type="number" min="0" step="any" value={position.x ?? ""} onChange={e => updateHolePosition(featureIndex, holeIndex, "x", e.target.value)} />
                <input disabled={loading || generating} aria-label={`Lỗ ${holeIndex + 1}, tọa độ Y`} type="number" min="0" step="any" value={position.y ?? ""} onChange={e => updateHolePosition(featureIndex, holeIndex, "y", e.target.value)} />
              </div>)}
            </div>
          </fieldset>
        ))}
        {plan.assumptions.length > 0 && <div><h3>Giả định</h3><ul>{plan.assumptions.map(item => <li key={item}>{item}</li>)}</ul></div>}
        {plan.warnings.length > 0 && <div className="warning"><h3>Cảnh báo</h3><ul>{plan.warnings.map(item => <li key={item}>{item}</li>)}</ul></div>}
        <details><summary>{edited ? "Ràng buộc sẽ được kiểm tra lại tại máy chủ" : "Ràng buộc đã kiểm tra"}</summary><ul>{plan.constraints.map(item => <li key={item}>{item}</li>)}</ul></details>
        <details><summary>CAD Plan JSON (v{plan.schema_version})</summary><pre>{JSON.stringify(plan, null, 2)}</pre></details>
      </section>}
      <footer>FreeCAD tạo mô hình trong Space. Bản hiện tại dùng parser xác định, chưa phải AI tổng quát; chỉ hỗ trợ đùn tấm chữ nhật và cắt lỗ xuyên. FCStd hiện chưa có Feature Tree tham số đầy đủ.</footer>
    </main>
  );
}
