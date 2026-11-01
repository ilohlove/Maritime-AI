export type Field = {
  key: string;
  label: string;
  unit?: string;
  type?: "number";
  step?: string;
  max?: number;
  min?: number;
};
export const groups: { title: string; fields: Field[] }[] = [
  {
    title: "Vessel identity",
    fields: [
      { key: "vessel_name", label: "Vessel Name" },
      { key: "former_name", label: "Former Name" },
      { key: "imo_number", label: "IMO Number" },
      { key: "mmsi", label: "MMSI" },
      { key: "call_sign", label: "Call Sign" },
      { key: "flag", label: "Flag" },
      { key: "port_of_registry", label: "Port of Registry" },
      { key: "vessel_type", label: "Vessel Type" },
      { key: "classification_society", label: "Classification Society" },
      {
        key: "year_built",
        label: "Year Built",
        type: "number",
        step: "1",
        min: 1800,
        max: 2100,
      },
    ],
  },
  {
    title: "Principal dimensions",
    fields: [
      {
        key: "length_overall",
        label: "Length Overall",
        unit: "m",
        type: "number",
      },
      {
        key: "length_between_perpendiculars",
        label: "Length Between Perpendiculars",
        unit: "m",
        type: "number",
      },
      {
        key: "breadth_moulded",
        label: "Breadth Moulded",
        unit: "m",
        type: "number",
      },
      {
        key: "depth_moulded",
        label: "Depth Moulded",
        unit: "m",
        type: "number",
      },
      { key: "summer_draft", label: "Summer Draft", unit: "m", type: "number" },
    ],
  },
  {
    title: "Tonnage",
    fields: [
      {
        key: "gross_tonnage",
        label: "Gross Tonnage",
        unit: "GT",
        type: "number",
        step: "1",
        max: 2000000000,
      },
      {
        key: "net_tonnage",
        label: "Net Tonnage",
        unit: "NT",
        type: "number",
        step: "1",
        max: 2000000000,
      },
      {
        key: "summer_deadweight",
        label: "Summer Deadweight",
        unit: "t",
        type: "number",
      },
    ],
  },
  {
    title: "Machinery",
    fields: [
      { key: "main_engine_manufacturer", label: "Main Engine Manufacturer" },
      { key: "main_engine_model", label: "Main Engine Model" },
      {
        key: "main_engine_power",
        label: "Main Engine Power",
        unit: "kW",
        type: "number",
      },
    ],
  },
];
export const fields = groups.flatMap((group) => group.fields);
