import { useEffect, useRef } from "react";

export function Waveform({ active }: { active: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    let raf = 0;
    const start = performance.now();
    const draw = () => {
      const t = (performance.now() - start) / 1000;
      const { width, height } = c;
      ctx.clearRect(0, 0, width, height);
      ctx.strokeStyle = active ? "#4cc9f0" : "#4361ee";
      ctx.lineWidth = 2;
      ctx.beginPath();
      const amp = active ? 18 : 4;
      for (let x = 0; x < width; x++) {
        const y = height / 2 + Math.sin(x * 0.04 + t * (active ? 6 : 1.5)) * amp +
          Math.sin(x * 0.012 + t * 2) * (amp / 2);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [active]);
  return <canvas ref={ref} width={600} height={60} style={{ width: "100%", height: 60 }} />;
}
