import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

export default function TrendChart({ trend, metric }) {
  const formatValue = (value) => metric.format(Number(value));
  return <ResponsiveContainer width="100%" height="100%"><LineChart data={trend} margin={{ top: 26, right: 34, bottom: 16, left: 12 }}><CartesianGrid stroke="#ddd6ca" vertical={false} strokeDasharray="3 5" /><XAxis dataKey="period" tickLine={false} axisLine={{ stroke: "#c9c1b5" }} tickMargin={12} tick={{ fill: "#625f58", fontSize: 12, fontWeight: 600 }} /><YAxis domain={["auto", "auto"]} tickFormatter={formatValue} tickLine={false} axisLine={false} width={72} tick={{ fill: "#625f58", fontSize: 11 }} /><Tooltip formatter={(value) => [formatValue(value), metric.label]} labelFormatter={(label) => `${label} · reported history`} cursor={{ stroke: "#9f9486", strokeDasharray: "3 4" }} contentStyle={{ background: "#fffdf8", border: "1px solid #d8d2c8", borderRadius: 6, fontSize: 12, boxShadow: "0 8px 24px rgba(25,24,21,.1)" }} /><Line type="monotone" dataKey={metric.key} name={metric.label} stroke={metric.color} strokeWidth={4} dot={{ r: 6, fill: "#fffdf8", stroke: metric.color, strokeWidth: 3 }} activeDot={{ r: 8, fill: metric.color, stroke: "#fffdf8", strokeWidth: 3 }} /></LineChart></ResponsiveContainer>;
}
