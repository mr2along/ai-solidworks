import { useState } from "react";

type Position = { x?: number; y?: number };
type Feature = {
  id: string;
  type: "extruded_plate" | "through_holes" | "through_slots" | "rectangular_pockets";
  length?: number | null;
  width?: number | null;
  thickness?: number | null;
  diameter?: number | null;
  positions?: Position[];
  slot_length?: number | null;
  slot_width?: number | null;
  pocket_length?: number | null;
  pocket_width?: number | null;
  pocket_depth?: number | null;
  orientation?: "x" | "y" | null;
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
type AssemblyPlacement = { x: number; y: number; z: number; rotation_z: 0 | 90 | 180 | 270 };
type AssemblyItem = { id: string; item_number: number; part_plan: Plan; placements: AssemblyPlacement[] };

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
  const slots = features.find(feature => feature.type === "through_slots");
  if (slots?.slot_length !== null && slots?.slot_length !== undefined) result.slot_length_mm = slots.slot_length;
  if (slots?.slot_width !== null && slots?.slot_width !== undefined) result.slot_width_mm = slots.slot_width;
  if (slots?.positions) {
    result.slot_count = slots.positions.length;
    slots.positions.forEach((position, index) => {
      if (position.x !== undefined) result[`slot_${index + 1}_x_mm`] = position.x;
      if (position.y !== undefined) result[`slot_${index + 1}_y_mm`] = position.y;
    });
  }
  const pockets = features.find(feature => feature.type === "rectangular_pockets");
  if (pockets?.pocket_length !== null && pockets?.pocket_length !== undefined) result.pocket_length_mm = pockets.pocket_length;
  if (pockets?.pocket_width !== null && pockets?.pocket_width !== undefined) result.pocket_width_mm = pockets.pocket_width;
  if (pockets?.pocket_depth !== null && pockets?.pocket_depth !== undefined) result.pocket_depth_mm = pockets.pocket_depth;
  if (pockets?.positions) {
    result.pocket_count = pockets.positions.length;
    pockets.positions.forEach((position, index) => {
      if (position.x !== undefined) result[`pocket_${index + 1}_x_mm`] = position.x;
      if (position.y !== undefined) result[`pocket_${index + 1}_y_mm`] = position.y;
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
  const [assemblyName, setAssemblyName] = useState("assembly_drawing");
  const [assemblyItems, setAssemblyItems] = useState<AssemblyItem[]>([]);
  const [assemblyGenerating, setAssemblyGenerating] = useState(false);
  const [assemblyError, setAssemblyError] = useState("");
  const [assemblySuccess, setAssemblySuccess] = useState("");

  function clearPreview() {
    setPlan(null);
    setEdited(false);
    setSuccess("");
  }

  function updateFeatureNumber(
    featureIndex: number,
    field: "length" | "width" | "thickness" | "diameter" | "slot_length" | "slot_width" | "pocket_length" | "pocket_width" | "pocket_depth",
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

  function updateCutPosition(featureIndex: number, positionIndex: number, axis: "x" | "y", rawValue: string) {
    const value = rawValue === "" ? undefined : Number(rawValue);
    if (value !== undefined && !Number.isFinite(value)) return;
    setPlan(current => {
      if (!current) return current;
      const features = current.features.map((feature, index) => {
        if (index !== featureIndex) return feature;
        return {
          ...feature,
          positions: feature.positions?.map((position, index) =>
            index === positionIndex ? { ...position, [axis]: value } : position
          )
        };
      });
      return { ...current, features, parameters: deriveParameters(features), constraints: [], validation: "pending_server_recheck" };
    });
    setEdited(true);
  }

  function updateSlotOrientation(featureIndex: number, orientation: "x" | "y") {
    setPlan(current => {
      if (!current) return current;
      const features = current.features.map((feature, index) =>
        index === featureIndex ? { ...feature, orientation } : feature
      );
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

  function addPlanToAssembly() {
    if (!plan) return;
    if (assemblyItems.length >= 12) {
      setAssemblyError("Bản vẽ lắp hiện giới hạn 12 dòng chi tiết.");
      return;
    }
    const maxX = assemblyItems.flatMap(item => item.placements.map(pose => {
      const partBase = item.part_plan.features[0];
      const xLength = pose.rotation_z % 180 ? (partBase.width ?? 0) : (partBase.length ?? 0);
      return pose.x + xLength;
    })).reduce((value, itemX) => Math.max(value, itemX), 0);
    const partPlan = { ...plan, validation: "passed" as const };
    const nextNumber = assemblyItems.reduce((value, item) => Math.max(value, item.item_number), 0) + 1;
    setAssemblyItems(items => [...items, {
      id: `component_${nextNumber}`,
      item_number: nextNumber,
      part_plan: partPlan,
      placements: [{ x: assemblyItems.length ? maxX + 10 : 0, y: 0, z: 0, rotation_z: 0 }]
    }]);
    setAssemblyError("");
    setAssemblySuccess("");
    setSuccess(`${plan.part_name} đã được thêm vào danh sách bản vẽ lắp.`);
  }

  function updateAssemblyPlacement(
    itemIndex: number,
    placementIndex: number,
    field: keyof AssemblyPlacement,
    rawValue: string
  ) {
    const value = field === "rotation_z" ? Number(rawValue) : Number(rawValue || 0);
    if (!Number.isFinite(value)) return;
    setAssemblyItems(items => items.map((item, currentIndex) => currentIndex !== itemIndex ? item : {
      ...item,
      placements: item.placements.map((pose, currentPose) => currentPose !== placementIndex ? pose : {
        ...pose,
        [field]: value
      })
    }));
    setAssemblyError("");
    setAssemblySuccess("");
  }

  function addAssemblyInstance(itemIndex: number) {
    const item = assemblyItems[itemIndex];
    if (!item || assemblyItems.reduce((sum, row) => sum + row.placements.length, 0) >= 30) {
      setAssemblyError("Bản vẽ lắp hiện giới hạn 30 vị trí chi tiết.");
      return;
    }
    const maxX = assemblyItems.flatMap(row => row.placements.map(pose => {
      const base = row.part_plan.features[0];
      const xLength = pose.rotation_z % 180 ? (base.width ?? 0) : (base.length ?? 0);
      return pose.x + xLength;
    })).reduce((value, itemX) => Math.max(value, itemX), 0);
    const previous = item.placements[item.placements.length - 1] ?? { y: 0, z: 0, rotation_z: 0 as const };
    setAssemblyItems(items => items.map((row, index) => index !== itemIndex ? row : {
      ...row,
      placements: [...row.placements, {
        x: maxX + 10,
        y: previous.y,
        z: previous.z,
        rotation_z: previous.rotation_z
      }]
    }));
    setAssemblySuccess("");
  }

  async function downloadAssemblyDrawing() {
    if (assemblyItems.reduce((sum, item) => sum + item.placements.length, 0) < 2) return;
    setAssemblyGenerating(true);
    setAssemblyError("");
    setAssemblySuccess("");
    try {
      const response = await fetch("/api/assembly/drawing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan: { schema_version: "1.0", assembly_name: assemblyName, units: "mm", items: assemblyItems }
        })
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        throw new Error(detail || `Không thể tạo bản vẽ lắp (HTTP ${response.status}).`);
      }
      const blob = await response.blob();
      if (blob.type !== "application/pdf" || blob.size === 0) {
        throw new Error("Backend không trả về file PDF bản vẽ lắp hợp lệ.");
      }
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${assemblyName}-drawing.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setAssemblySuccess("Bản vẽ lắp PDF đã được tạo và đang tải xuống.");
    } catch (e) {
      setAssemblyError(e instanceof Error ? e.message : "Lỗi khi tạo bản vẽ lắp.");
    } finally {
      setAssemblyGenerating(false);
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
        <p className="muted">Hỗ trợ tấm chữ nhật, 4 lỗ xuyên, rãnh xuyên bo tròn và hốc chữ nhật mù. Hãy ghi rõ kích thước, độ sâu, vị trí tâm và rà soát CAD Plan trước khi tạo.</p>
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
        ) : feature.type === "through_holes" ? (
          <fieldset className="featureEditor" key={feature.id}>
            <legend>Feature {featureIndex + 1}: Lỗ xuyên</legend>
            <label>Đường kính (mm)
              <input disabled={loading || generating} type="number" min="0" step="any" value={feature.diameter ?? ""} onChange={e => updateFeatureNumber(featureIndex, "diameter", e.target.value)} />
            </label>
            <div className="holeGrid"><strong>Lỗ</strong><strong>Tâm X (mm)</strong><strong>Tâm Y (mm)</strong>
              {feature.positions?.map((position, holeIndex) => <div className="holeRow" key={holeIndex}>
                <span>{holeIndex + 1}</span>
                <input disabled={loading || generating} aria-label={`Lỗ ${holeIndex + 1}, tọa độ X`} type="number" min="0" step="any" value={position.x ?? ""} onChange={e => updateCutPosition(featureIndex, holeIndex, "x", e.target.value)} />
                <input disabled={loading || generating} aria-label={`Lỗ ${holeIndex + 1}, tọa độ Y`} type="number" min="0" step="any" value={position.y ?? ""} onChange={e => updateCutPosition(featureIndex, holeIndex, "y", e.target.value)} />
              </div>)}
            </div>
          </fieldset>
        ) : feature.type === "through_slots" ? (
          <fieldset className="featureEditor" key={feature.id}>
            <legend>Feature {featureIndex + 1}: Rãnh xuyên bo tròn</legend>
            <label>Dài tổng thể (mm)
              <input disabled={loading || generating} type="number" min="0" step="any" value={feature.slot_length ?? ""} onChange={e => updateFeatureNumber(featureIndex, "slot_length", e.target.value)} />
            </label>
            <label>Rộng (mm)
              <input disabled={loading || generating} type="number" min="0" step="any" value={feature.slot_width ?? ""} onChange={e => updateFeatureNumber(featureIndex, "slot_width", e.target.value)} />
            </label>
            <label>Trục dài
              <select disabled={loading || generating} value={feature.orientation ?? "x"} onChange={e => updateSlotOrientation(featureIndex, e.target.value as "x" | "y")}>
                <option value="x">Theo X</option><option value="y">Theo Y</option>
              </select>
            </label>
            <div className="holeGrid"><strong>Rãnh</strong><strong>Tâm X (mm)</strong><strong>Tâm Y (mm)</strong>
              {feature.positions?.map((position, slotIndex) => <div className="holeRow" key={slotIndex}>
                <span>{slotIndex + 1}</span>
                <input disabled={loading || generating} aria-label={`Rãnh ${slotIndex + 1}, tọa độ X`} type="number" min="0" step="any" value={position.x ?? ""} onChange={e => updateCutPosition(featureIndex, slotIndex, "x", e.target.value)} />
                <input disabled={loading || generating} aria-label={`Rãnh ${slotIndex + 1}, tọa độ Y`} type="number" min="0" step="any" value={position.y ?? ""} onChange={e => updateCutPosition(featureIndex, slotIndex, "y", e.target.value)} />
              </div>)}
            </div>
          </fieldset>
        ) : (
          <fieldset className="featureEditor" key={feature.id}>
            <legend>Feature {featureIndex + 1}: Hốc chữ nhật mù</legend>
            <label>Dài theo X (mm)
              <input disabled={loading || generating} type="number" min="0" step="any" value={feature.pocket_length ?? ""} onChange={e => updateFeatureNumber(featureIndex, "pocket_length", e.target.value)} />
            </label>
            <label>Rộng theo Y (mm)
              <input disabled={loading || generating} type="number" min="0" step="any" value={feature.pocket_width ?? ""} onChange={e => updateFeatureNumber(featureIndex, "pocket_width", e.target.value)} />
            </label>
            <label>Độ sâu từ mặt trên (mm)
              <input disabled={loading || generating} type="number" min="0" step="any" value={feature.pocket_depth ?? ""} onChange={e => updateFeatureNumber(featureIndex, "pocket_depth", e.target.value)} />
            </label>
            <div className="holeGrid"><strong>Hốc</strong><strong>Tâm X (mm)</strong><strong>Tâm Y (mm)</strong>
              {feature.positions?.map((position, pocketIndex) => <div className="holeRow" key={pocketIndex}>
                <span>{pocketIndex + 1}</span>
                <input disabled={loading || generating} aria-label={`Hốc ${pocketIndex + 1}, tọa độ X`} type="number" min="0" step="any" value={position.x ?? ""} onChange={e => updateCutPosition(featureIndex, pocketIndex, "x", e.target.value)} />
                <input disabled={loading || generating} aria-label={`Hốc ${pocketIndex + 1}, tọa độ Y`} type="number" min="0" step="any" value={position.y ?? ""} onChange={e => updateCutPosition(featureIndex, pocketIndex, "y", e.target.value)} />
              </div>)}
            </div>
          </fieldset>
        ))}
        {plan.assumptions.length > 0 && <div><h3>Giả định</h3><ul>{plan.assumptions.map(item => <li key={item}>{item}</li>)}</ul></div>}
        <button className="secondary" onClick={addPlanToAssembly} disabled={loading || generating || assemblyGenerating}>
          Thêm chi tiết này vào bản vẽ lắp
        </button>
        {plan.warnings.length > 0 && <div className="warning"><h3>Cảnh báo</h3><ul>{plan.warnings.map(item => <li key={item}>{item}</li>)}</ul></div>}
        <details><summary>{edited ? "Ràng buộc sẽ được kiểm tra lại tại máy chủ" : "Ràng buộc đã kiểm tra"}</summary><ul>{plan.constraints.map(item => <li key={item}>{item}</li>)}</ul></details>
        <details><summary>CAD Plan JSON (v{plan.schema_version})</summary><pre>{JSON.stringify(plan, null, 2)}</pre></details>
      </section>}
      <section className="panel">
        <h2>Bản vẽ lắp ráp</h2>
        <p className="muted">Thêm các CAD Plan đã tạo ở trên, rồi nhập vị trí lắp X/Y/Z và góc quay quanh Z cho từng chi tiết. X/Y là góc dưới-trái của footprint sau khi quay; Z là mặt đáy. Vị trí khởi tạo được xếp tách nhau để dễ chỉnh. Bản vẽ gồm hình trục đo, ba hình chiếu và bảng kê.</p>
        <div className="warning"><strong>Phạm vi hiện tại:</strong> chỉ lắp các chi tiết dạng tấm với feature đang được hỗ trợ. Vị trí do bạn nhập; hệ thống chưa kiểm tra mặt lắp, va chạm, dung sai hay độ khớp.</div>
        <label htmlFor="assemblyName">Tên cụm lắp</label>
        <input id="assemblyName" disabled={assemblyGenerating} value={assemblyName} onChange={event => { setAssemblyName(event.target.value); setAssemblySuccess(""); }} maxLength={60} pattern="[A-Za-z0-9_-]+" />
        {assemblyItems.length === 0 ? <p className="muted">Chưa có chi tiết. Hãy tạo CAD Plan và chọn “Thêm chi tiết này vào bản vẽ lắp”.</p> : (
          <div className="assemblyItems">
            {assemblyItems.map((item, itemIndex) => {
              const base = item.part_plan.features[0];
              return <fieldset className="assemblyItem" key={item.id}>
                <legend>Item {item.item_number}: {item.part_plan.part_name} · {item.placements.length} vị trí</legend>
                <div className="assemblyActions">
                  <button className="smallButton" onClick={() => addAssemblyInstance(itemIndex)} disabled={assemblyGenerating}>Thêm một bản sao</button>
                  <button className="smallButton dangerButton" onClick={() => { setAssemblyItems(items => items.filter((_, index) => index !== itemIndex)); setAssemblySuccess(""); }} disabled={assemblyGenerating}>Xóa chi tiết</button>
                </div>
                {item.placements.map((pose, poseIndex) => <div className="placementRow" key={`${item.id}-${poseIndex}`}>
                  <strong>Vị trí {poseIndex + 1}</strong>
                  {([ ["x", "X (mm)"], ["y", "Y (mm)"], ["z", "Z (mm)"] ] as const).map(([field, label]) => (
                    <label key={field}>{label}<input disabled={assemblyGenerating} type="number" min="-5000" max="5000" step="any" value={pose[field]} onChange={event => updateAssemblyPlacement(itemIndex, poseIndex, field, event.target.value)} /></label>
                  ))}
                  <label>Quay quanh Z<select disabled={assemblyGenerating} value={pose.rotation_z} onChange={event => updateAssemblyPlacement(itemIndex, poseIndex, "rotation_z", event.target.value)}>
                    <option value={0}>0°</option><option value={90}>90°</option><option value={180}>180°</option><option value={270}>270°</option>
                  </select></label>
                  {item.placements.length > 1 && <button className="smallButton dangerButton removePose" disabled={assemblyGenerating} onClick={() => { setAssemblyItems(items => items.map((row, index) => index !== itemIndex ? row : { ...row, placements: row.placements.filter((_, index) => index !== poseIndex) })); setAssemblySuccess(""); }}>Xóa vị trí</button>}
                </div>)}
                <p className="muted">Kích thước chi tiết gốc: {base.length} × {base.width} × {base.thickness} mm.</p>
              </fieldset>;
            })}
          </div>
        )}
        <button onClick={downloadAssemblyDrawing} disabled={assemblyGenerating || assemblyItems.reduce((sum, item) => sum + item.placements.length, 0) < 2 || !/^[A-Za-z0-9_-]+$/.test(assemblyName)}>
          {assemblyGenerating ? "Đang xuất PDF…" : "Tạo bản vẽ lắp PDF"}
        </button>
        {assemblyError && <div className="error" role="alert">{assemblyError}</div>}
        {assemblySuccess && <div className="successMessage" role="status">{assemblySuccess}</div>}
      </section>
      <footer>FreeCAD tạo file chi tiết trong Space. Bản vẽ lắp PDF hiện dùng các CAD Plan dạng tấm được hỗ trợ, với vị trí do người dùng nhập; chưa tạo assembly native hoặc kiểm tra va chạm, mặt lắp và dung sai. Parser hiện hỗ trợ tấm chữ nhật, 4 lỗ xuyên, rãnh xuyên bo tròn và hốc chữ nhật mù. FCStd chi tiết hiện lưu một solid cùng thuộc tính kích thước, chưa có Feature Tree tham số đầy đủ.</footer>
    </main>
  );
}
