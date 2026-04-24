export function formatPercent(value: number, digits = 1) {
  return `${value.toFixed(digits)}%`;
}

export function formatNumber(value: number) {
  return new Intl.NumberFormat("fr-TN").format(value);
}

export function formatCompactNumber(value: number) {
  return new Intl.NumberFormat("fr-TN", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatDate(value?: string | null) {
  if (!value) return "N/A";
  return new Intl.DateTimeFormat("fr-TN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatLatency(value: number) {
  return `${value.toFixed(1)} ms`;
}

export function formatPacketLoss(value: number) {
  return `${value.toFixed(2)} %`;
}

export function formatThroughput(value: number) {
  return `${value.toFixed(1)} Mbps`;
}

export function formatScore(value: number, digits = 2) {
  return value.toFixed(digits);
}

export function clamp(value: number, min = 0, max = 100) {
  return Math.min(Math.max(value, min), max);
}

export function truncateText(value: string, length = 72) {
  if (value.length <= length) return value;
  return `${value.slice(0, length - 1)}...`;
}
