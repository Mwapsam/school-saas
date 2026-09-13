"use client";

import * as React from "react";
import { Eraser, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SignaturePadProps {
  value?: string;
  onChange: (dataUrl: string) => void;
  disabled?: boolean;
  className?: string;
  width?: number;
  height?: number;
}

export function SignaturePad({
  value,
  onChange,
  disabled = false,
  className,
  width = 320,
  height = 110,
}: SignaturePadProps) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const drawing = React.useRef(false);
  const lastPos = React.useRef({ x: 0, y: 0 });
  const hasStrokes = React.useRef(false);
  const fileRef = React.useRef<HTMLInputElement>(null);
  const prevValue = React.useRef("");

  // When a saved value arrives, draw it onto the canvas.
  React.useEffect(() => {
    if (!value || value === prevValue.current) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const img = new Image();
    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const scale = Math.min(canvas.width / img.width, canvas.height / img.height, 1);
      const w = img.width * scale;
      const h = img.height * scale;
      ctx.drawImage(img, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
      hasStrokes.current = true;
      prevValue.current = value;
    };
    img.src = value;
  }, [value]);

  function getPos(e: React.MouseEvent | React.TouchEvent) {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const src = "touches" in e ? e.touches[0] : e;
    return { x: src.clientX - rect.left, y: src.clientY - rect.top };
  }

  function onStart(e: React.MouseEvent | React.TouchEvent) {
    if (disabled) return;
    e.preventDefault();
    drawing.current = true;
    lastPos.current = getPos(e);
  }

  function onMove(e: React.MouseEvent | React.TouchEvent) {
    if (!drawing.current || disabled) return;
    e.preventDefault();
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    const pos = getPos(e);
    ctx.beginPath();
    ctx.moveTo(lastPos.current.x, lastPos.current.y);
    ctx.lineTo(pos.x, pos.y);
    ctx.strokeStyle = "#0f172a";
    ctx.lineWidth = 1.8;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.stroke();
    lastPos.current = pos;
    hasStrokes.current = true;
  }

  function onEnd() {
    if (!drawing.current) return;
    drawing.current = false;
    const canvas = canvasRef.current;
    if (canvas && hasStrokes.current) {
      const dataUrl = canvas.toDataURL("image/png");
      prevValue.current = dataUrl;
      onChange(dataUrl);
    }
  }

  function handleClear() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.getContext("2d")!.clearRect(0, 0, canvas.width, canvas.height);
    hasStrokes.current = false;
    prevValue.current = "";
    onChange("");
  }

  function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const src = ev.target?.result as string;
      const img = new Image();
      img.onload = () => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d")!;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const scale = Math.min(canvas.width / img.width, canvas.height / img.height, 1);
        const w = img.width * scale;
        const h = img.height * scale;
        ctx.drawImage(img, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
        hasStrokes.current = true;
        const dataUrl = canvas.toDataURL("image/png");
        prevValue.current = dataUrl;
        onChange(dataUrl);
      };
      img.src = src;
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }

  const isEmpty = !value;

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="relative">
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          style={{ touchAction: "none", display: "block" }}
          className={cn(
            "rounded-lg bg-white transition-colors",
            disabled
              ? "cursor-not-allowed opacity-60 border border-border"
              : "cursor-crosshair border-2 border-dashed border-muted-foreground/30 hover:border-primary/40",
          )}
          onMouseDown={onStart}
          onMouseMove={onMove}
          onMouseUp={onEnd}
          onMouseLeave={onEnd}
          onTouchStart={onStart}
          onTouchMove={onMove}
          onTouchEnd={onEnd}
        />
        {/* Empty state hint — pointer-events-none so canvas still receives input */}
        {isEmpty && !disabled && (
          <div
            className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-1.5 rounded-lg"
            aria-hidden
          >
            <svg
              className="h-7 w-7 text-muted-foreground/30"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125"
              />
            </svg>
            <span className="text-xs font-medium text-muted-foreground/50">
              Draw your signature here
            </span>
          </div>
        )}
      </div>

      {!disabled && (
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleClear}
            className="h-8 gap-1.5 px-2.5 text-xs text-muted-foreground hover:text-foreground"
            disabled={isEmpty}
          >
            <Eraser className="h-3.5 w-3.5" />
            Clear
          </Button>
          <span className="text-muted-foreground/40 text-xs">or</span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => fileRef.current?.click()}
            className="h-8 gap-1.5 px-2.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <Upload className="h-3.5 w-3.5" />
            Upload image
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleUpload}
          />
        </div>
      )}
    </div>
  );
}
