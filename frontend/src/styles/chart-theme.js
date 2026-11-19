// Chart treatments informed by Unslop (Damir Sokolovsky, CC BY 4.0).
export const chartPalette = {
  ink: '#273238', muted: '#626e74', grid: '#e8ece8', low: '#c7d2cc',
  mid: '#d4b171', high: '#a84039', accent: '#345fc5', blank: '#dce1dd',
}
export const chartTheme = {
  color: [chartPalette.accent, chartPalette.mid, chartPalette.high, '#7d9085'],
  textStyle: { fontFamily: 'Segoe UI, Microsoft YaHei, sans-serif', fontSize: 12, color: chartPalette.muted },
  legend: { textStyle: { color: chartPalette.muted, fontSize: 12 }, itemWidth: 12, itemHeight: 8, itemGap: 20 },
  tooltip: { backgroundColor: '#ffffff', borderColor: '#dfe3e1', borderWidth: 1, padding: [12,16], textStyle: { color: chartPalette.ink, fontSize: 12 }, extraCssText: 'box-shadow:0 6px 24px #20282e14;border-radius:10px;line-height:1.8;' },
  categoryAxis: { axisLine: { lineStyle: { color: '#ccd4cd' } }, axisTick: { show: false }, axisLabel: { color: chartPalette.muted, fontSize: 11 }, splitLine: { lineStyle: { color: chartPalette.grid } }, splitArea: { areaStyle: { color: ['#fafbf9','#f2f5f1'] } } },
  valueAxis: { axisLabel: { color: chartPalette.muted, fontSize: 11 }, splitLine: { lineStyle: { color: chartPalette.grid } } },
  visualMap: { textStyle: { color: chartPalette.muted, fontSize: 11 }, itemWidth: 10, itemHeight: 10, itemGap: 20 },
}
