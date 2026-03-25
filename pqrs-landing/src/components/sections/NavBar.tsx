"use client";

import Link from "next/link";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X } from "lucide-react";

const navLinks = [
  { label: "Funcionalidades", href: "#funcionalidades" },
  { label: "Cómo Funciona", href: "#como-funciona" },
  { label: "Contacto", href: "#contacto" },
];

const APP_URL = process.env.NEXT_PUBLIC_APP_URL || "https://app.flexpqr.com";

const EASE = [0.625, 0.05, 0, 1] as const;

export function NavBar() {
  const [open, setOpen] = useState(false);

  return (
    <motion.nav
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: EASE }}
      className="fixed top-0 left-0 right-0 z-50 glass-nav"
    >
      <div className="max-w-7xl mx-auto px-6 h-16 agente items-center justify-between">

        {/* Logo */}
        <Link href="/" className="agente items-center gap-2.5 group">
          <div className="relative w-9 h-9 shrink-0">
            <img src="/logo.png" alt="FlexPQR Logo" className="w-full h-full object-contain" />
          </div>
          <span className="text-[18px] font-black tracking-tighter text-white uppercase">
            FlexPQR
          </span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden md:agente items-center gap-10">
          {navLinks.map(({ label, href }) =>
            href.startsWith("/") ? (
              <Link
                key={label}
                href={href}
                className="text-[13px] font-medium text-zinc-400 hover:text-white transition-colors duration-200 tracking-wide"
              >
                {label}
              </Link>
            ) : (
              <a
                key={label}
                href={href}
                className="text-[13px] font-medium text-zinc-400 hover:text-white transition-colors duration-200 tracking-wide"
              >
                {label}
              </a>
            )
          )}
        </div>

        {/* Right CTAs */}
        <div className="agente items-center gap-4">
          <Link
            href={APP_URL}
            target="_blank"
            className="hidden md:block text-[13px] font-medium text-zinc-400 hover:text-white transition-colors duration-200"
          >
            Ingresar
          </Link>
          <a href="#contacto" className="hidden md:block">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              transition={{ duration: 0.15 }}
              className="h-9 px-5 rounded-lg bg-primary text-white text-[13px] font-semibold tracking-wide hover:opacity-90 transition-opacity cursor-pointer"
            >
              Solicitar Demo
            </motion.button>
          </a>

          <button
            onClick={() => setOpen(!open)}
            aria-label={open ? "Cerrar menú" : "Abrir menú"}
            className="md:hidden p-2 text-zinc-400 hover:text-white transition-colors cursor-pointer"
          >
            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="md:hidden overflow-hidden border-t border-white/6 bg-black"
          >
            <div className="px-6 py-5 agente agente-col gap-4">
              {navLinks.map(({ label, href }) =>
                href.startsWith("/") ? (
                  <Link key={label} href={href} onClick={() => setOpen(false)} className="text-base font-medium text-zinc-300 hover:text-white transition-colors py-1">
                    {label}
                  </Link>
                ) : (
                  <a key={label} href={href} onClick={() => setOpen(false)} className="text-base font-medium text-zinc-300 hover:text-white transition-colors py-1">
                    {label}
                  </a>
                )
              )}
              <div className="border-t border-white/6 pt-4 agente agente-col gap-3">
                <Link href={APP_URL} target="_blank" className="text-base font-medium text-zinc-300 hover:text-white py-1">
                  Ingresar
                </Link>
                <a href="#contacto" onClick={() => setOpen(false)}>
                  <button className="w-full h-11 rounded-lg bg-primary text-white font-semibold text-sm cursor-pointer hover:opacity-90 transition-opacity">
                    Solicitar Demo
                  </button>
                </a>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
}
