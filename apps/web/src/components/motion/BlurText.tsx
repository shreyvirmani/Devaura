"use client";

import React, { useRef, useEffect, useState } from "react";
import { motion, useInView } from "motion/react";

interface BlurTextProps {
  text: string;
  delay?: number;
  className?: string;
  animateBy?: "words" | "letters";
  direction?: "top" | "bottom";
  threshold?: number;
  rootMargin?: string;
  onAnimationComplete?: () => void;
}

export function BlurText({
  text = "",
  delay = 120,
  className = "",
  animateBy = "words",
  direction = "top",
  threshold = 0.1,
  rootMargin = "-50px",
  onAnimationComplete,
}: BlurTextProps) {
  const elements = animateBy === "words" ? text.split(" ") : text.split("");
  const [inView, setInView] = useState(false);
  const ref = useRef<HTMLParagraphElement>(null);
  const inViewResult = useInView(ref, { once: true, amount: threshold });

  useEffect(() => {
    if (inViewResult) {
      setInView(true);
    }
  }, [inViewResult]);

  const defaultFrom = {
    filter: "blur(8px)",
    opacity: 0,
    y: direction === "top" ? -12 : 12,
  };

  const defaultTo = {
    filter: "blur(0px)",
    opacity: 1,
    y: 0,
  };

  return (
    <p ref={ref} className={`flex flex-wrap ${className}`}>
      {elements.map((element, i) => (
        <motion.span
          key={i}
          initial={defaultFrom}
          animate={inView ? defaultTo : defaultFrom}
          transition={{
            duration: 0.24,
            delay: (i * delay) / 1000,
            ease: [0.16, 1, 0.3, 1],
          }}
          className="inline-block will-change-transform will-change-filter"
          onAnimationComplete={
            i === elements.length - 1 ? onAnimationComplete : undefined
          }
        >
          {element}
          {animateBy === "words" && i < elements.length - 1 && (
            <span className="inline-block">&nbsp;</span>
          )}
        </motion.span>
      ))}
    </p>
  );
}

export default BlurText;
