import { useState, type FormEvent } from "react";
import { ApiError, request, type Vessel } from "./api";
import { fields, groups } from "./fields";

type Props = { vessel: Vessel | null; onSaved: (vessel: Vessel) => void };
export function ShipProfile({ vessel, onSaved }: Props) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      fields.map((field) => [field.key, String(vessel?.[field.key] ?? "")]),
    ),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState<Set<string>>(new Set());

  async function save(event: FormEvent) {
    event.preventDefault();
    const problems: Record<string, string> = {};
    for (const field of fields) {
      const value = values[field.key].trim();
      if (!value) continue;
      if (value.length > 200)
        problems[field.key] = "Use 200 characters or fewer.";
      if (field.type === "number") {
        const number = Number(value);
        if (
          !Number.isFinite(number) ||
          number < (field.min ?? 0.001) ||
          number > (field.max ?? 99999999999.999)
        )
          problems[field.key] =
            "Enter a positive number within the permitted range.";
        if (field.step === "1" && !Number.isInteger(number))
          problems[field.key] = "Enter a whole number.";
        if (field.step !== "1" && !/^\d+(?:\.\d{1,3})?$/.test(value))
          problems[field.key] = "Use up to three decimal places.";
      }
    }
    const imo = values.imo_number.trim();
    if (
      imo &&
      (!/^\d{7}$/.test(imo) ||
        [...imo.slice(0, 6)].reduce(
          (sum, digit, index) => sum + Number(digit) * (7 - index),
          0,
        ) %
          10 !==
          Number(imo[6]))
    )
      problems.imo_number =
        "Enter a valid 7-digit IMO number, including its checksum.";
    if (values.mmsi.trim() && !/^\d{9}$/.test(values.mmsi.trim()))
      problems.mmsi = "Enter exactly 9 digits.";
    if (
      values.year_built &&
      (Number(values.year_built) < 1800 || Number(values.year_built) > 2100)
    )
      problems.year_built = "Enter a year from 1800 to 2100.";
    if (
      values.net_tonnage &&
      values.gross_tonnage &&
      Number(values.net_tonnage) > Number(values.gross_tonnage)
    )
      problems.net_tonnage = "Net tonnage must not exceed gross tonnage.";
    if (
      values.length_between_perpendiculars &&
      values.length_overall &&
      Number(values.length_between_perpendiculars) >
        Number(values.length_overall)
    )
      problems.length_between_perpendiculars =
        "Must not exceed length overall.";
    setErrors(problems);
    if (Object.keys(problems).length) {
      setStatus("Review the highlighted fields.");
      return;
    }
    const payload: Record<string, unknown> = {};
    for (const field of fields) {
      // PATCH only changed fields to preserve provenance of unchanged values.
      if (vessel && !dirty.has(field.key)) continue;
      const value = values[field.key].trim();
      payload[field.key] = !value
        ? null
        : field.step === "1"
          ? Number(value)
          : value;
    }
    setSaving(true);
    setStatus("");
    try {
      const saved = await request<Vessel>(
        vessel ? `/vessels/${vessel.id}` : "/vessels",
        {
          method: vessel ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      onSaved(saved);
      setDirty(new Set());
      setStatus("Ship profile saved.");
    } catch (error) {
      if (error instanceof ApiError) setErrors(error.details);
      setStatus(
        error instanceof Error ? error.message : "Unable to save profile.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} noValidate>
      <div className="section-heading">
        <div>
          <h2>Vessel particulars</h2>
          <p>Leave unknown values blank. No information is inferred.</p>
        </div>
        <span className="pill">
          {vessel ? "Stored in private workspace" : "New profile"}
        </span>
      </div>
      {groups.map((group) => (
        <fieldset className="card" key={group.title}>
          <legend>{group.title}</legend>
          <div className="field-grid">
            {group.fields.map((field) => {
              const metadata = vessel?.field_provenance[field.key];
              return (
                <div className="field" key={field.key}>
                  <label htmlFor={field.key}>
                    {field.label}
                    {field.unit && (
                      <span className="unit"> ({field.unit})</span>
                    )}
                  </label>
                  <input
                    id={field.key}
                    name={field.key}
                    type={field.type ?? "text"}
                    value={values[field.key]}
                    maxLength={200}
                    min={field.min ?? 0.001}
                    max={field.max}
                    step={field.step ?? "0.001"}
                    aria-invalid={Boolean(errors[field.key])}
                    aria-describedby={`${field.key}-help`}
                    disabled={saving}
                    onChange={(event) => {
                      setValues({ ...values, [field.key]: event.target.value });
                      setDirty(new Set(dirty).add(field.key));
                    }}
                  />
                  <small
                    id={`${field.key}-help`}
                    className={errors[field.key] ? "error" : "field-meta"}
                  >
                    {errors[field.key] ||
                      (dirty.has(field.key)
                        ? "User entered · Unverified (pending save)"
                        : metadata
                          ? `${metadata.extraction_method.replaceAll("_", " ")} · ${metadata.verification_status}${metadata.source_document ? ` · ${metadata.source_document}` : ""} · ${new Date(metadata.last_updated).toLocaleString()}`
                          : "Unknown / not recorded")}
                  </small>
                </div>
              );
            })}
          </div>
        </fieldset>
      ))}
      <div className="save-bar">
        <p role="status" aria-live="polite">
          {status}
        </p>
        <button className="primary" type="submit" disabled={saving}>
          {saving ? "Saving…" : vessel ? "Save changes" : "Create ship profile"}
        </button>
      </div>
      {errors._form && (
        <p role="alert" className="error">
          {errors._form}
        </p>
      )}
    </form>
  );
}
