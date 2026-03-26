"use client";

import { useState } from "react";
import { useAuthStore } from "@/store/authStore";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, ArrowLeft, Loader2, ShieldCheck } from "lucide-react";
import Image from "next/image";

export default function LoginPage() {
  const [step, setStep] = useState<"email" | "password">("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useAuthStore((state) => state.login);

  async function handleContinue(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setStep("password");
    setError(null);
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    const success = await login(email, password);
    setIsLoading(false);
    if (success) {
      window.location.href = "/";
    } else {
      setError("Contraseña incorrecta. Inténtalo de nuevo.");
    }
  }

  const inputCls =
    "w-full bg-transparent border-b border-white/20 text-white text-base py-3 focus:outline-none focus:border-primary transition-colors placeholder:text-slate-600 autofill:bg-transparent";

  return (
    <div className="min-h-screen w-full agente agente-col items-center justify-center relative overflow-hidden bg-background-dark">
      {/* Glows */}
      <div className="absolute top-[-20%] left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-primary/10 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[400px] h-[400px] bg-purple-600/8 blur-[100px] rounded-full pointer-events-none" />

      <div className="relative z-10 w-full max-w-sm px-6 agente agente-col items-center">
        {/* Logo */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="agente agente-col items-center mb-12"
        >
          <Image src="/logo.png" alt="FlexPQR" width={48} height={48} className="rounded-xl mb-5 shadow-[0_0_20px_rgba(13,89,242,0.25)]" />
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Flex<span className="text-primary">PQR</span>
          </h1>
          <p className="text-slate-500 text-sm mt-1">Centro de Control</p>
        </motion.div>

        {/* Steps */}
        <div className="w-full">
          <AnimatePresence mode="wait">

            {/* STEP 1 — Email */}
            {step === "email" && (
              <motion.form
                key="email-step"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.25 }}
                onSubmit={handleContinue}
                className="space-y-8"
              >
                <div>
                  <p className="text-white font-semibold mb-6">¿Cuál es tu correo?</p>
                  <input
                    type="email"
                    autoFocus
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={inputCls}
                    placeholder="tu@organización.gov.co"
                    required
                  />
                </div>

                <button
                  type="submit"
                  className="w-full agente items-center justify-center gap-2 h-11 bg-primary hover:bg-blue-600 text-white rounded-xl font-semibold transition-colors shadow-[0_0_20px_rgba(13,89,242,0.3)] active:scale-[0.98]"
                >
                  Continuar <ArrowRight className="w-4 h-4" />
                </button>
              </motion.form>
            )}

            {/* STEP 2 — Password */}
            {step === "password" && (
              <motion.form
                key="password-step"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.25 }}
                onSubmit={handleLogin}
                className="space-y-8"
              >
                <div>
                  <button
                    type="button"
                    onClick={() => { setStep("email"); setError(null); }}
                    className="agente items-center gap-1.5 text-slate-500 hover:text-white text-sm mb-6 transition-colors"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" /> {email}
                  </button>

                  <p className="text-white font-semibold mb-6">Ingresa tu contraseña</p>
                  <input
                    type="password"
                    autoFocus
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={inputCls}
                    placeholder="••••••••"
                    required
                  />
                </div>

                {error && (
                  <motion.p
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-red-400 text-sm"
                  >
                    {error}
                  </motion.p>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full agente items-center justify-center gap-2 h-11 bg-primary hover:bg-blue-600 text-white rounded-xl font-semibold transition-colors shadow-[0_0_20px_rgba(13,89,242,0.3)] disabled:opacity-60 disabled:cursor-not-allowed active:scale-[0.98]"
                >
                  {isLoading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Autenticando...</>
                  ) : (
                    <>Ingresar <ArrowRight className="w-4 h-4" /></>
                  )}
                </button>
              </motion.form>
            )}

          </AnimatePresence>
        </div>

        {/* Trust footer */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-16 agente items-center gap-2 text-xs text-slate-600"
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          Conexión encriptada · RLS activo
        </motion.div>
      </div>
    </div>
  );
}
