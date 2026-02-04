"use client";

import React, { useState } from 'react';
import { Spinner } from "@blueprintjs/core";
import { ShieldCheck, Github, Mail, ArrowRight, Lock } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { BackgroundLines } from '@/components/ui/background-lines';
import { motion } from 'framer-motion';
import { useAuthStore } from '@/store/useAuthStore';
import { TextGenerateEffect } from '@/components/ui/text-generate-effect';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const login = useAuthStore((state) => state.login);

  const handleLogin = async (provider: 'google' | 'github') => {
    setLoading(true);
    console.log(`[Preciso Auth] Handshaking with ${provider}...`);
    
    // Simulate successful login
    setTimeout(() => {
      login({ email: 'sangmin@preciso-data.com', name: 'Sangmin Lee' });
      router.push('/cases');
    }, 1500);
  };

  const handleEmailLogin = async () => {
    if (!email) return;
    setLoading(true);
    // Simulate successful login
    setTimeout(() => {
      login({ email, name: 'Sovereign User' });
      router.push('/cases');
    }, 1500);
  };

  return (
    <BackgroundLines className="flex flex-col items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-[#2B95D6]/10 border border-[#2B95D6]/20 mb-4">
            <Lock className="text-[#2B95D6]" size={32} />
          </div>
          <h1 className="text-3xl font-bold tracking-tighter text-[#f6f7f9] mb-2">
            <TextGenerateEffect words="PRECISO GATEWAY" className="inline" />
          </h1>
          <p className="text-[#5c7080] text-xs font-mono tracking-widest uppercase">
            Sovereign Handshake Protocol Active
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-[#152127]/80 backdrop-blur-xl border border-[#30404d] p-8 shadow-[0_0_50px_-12px_rgba(43,149,214,0.3)] rounded-3xl relative overflow-hidden">
          <div className="relative z-10 space-y-6">
            
            {/* OAuth Buttons */}
            <div className="grid grid-cols-2 gap-4">
              <button 
                onClick={() => handleLogin('google')}
                className="flex items-center justify-center gap-2 py-3 px-4 bg-[#1a1c1e] hover:bg-[#1C2B33] border border-[#30404d] rounded-xl transition-all group"
              >
                <svg className="w-4 h-4 text-[#f6f7f9] group-hover:scale-110 transition-transform" viewBox="0 0 24 24">
                  <path fill="currentColor" d="M12.545,10.239v3.821h5.445c-0.712,2.315-2.647,3.972-5.445,3.972c-3.332,0-6.033-2.53-6.033-5.652s2.701-5.652,6.033-5.652c1.489,0,2.825,0.512,3.877,1.353l2.861-2.909C17.433,3.586,15.138,2.713,12.545,2.713c-5.422,0-9.827,4.405-9.827,9.827s4.405,9.827,9.827,9.827c4.689,0,8.736-3.375,9.65-7.854L12.545,10.239z"/>
                </svg>
                <span className="text-[10px] font-bold tracking-widest uppercase">Google</span>
              </button>
              <button 
                onClick={() => handleLogin('github')}
                className="flex items-center justify-center gap-2 py-3 px-4 bg-[#1a1c1e] hover:bg-[#1C2B33] border border-[#30404d] rounded-xl transition-all group"
              >
                <Github size={16} className="text-[#f6f7f9] group-hover:scale-110 transition-transform" />
                <span className="text-[10px] font-bold tracking-widest uppercase">Github</span>
              </button>
            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-[#30404d]"></div>
              </div>
              <div className="relative flex justify-center text-[9px] uppercase tracking-widest">
                <span className="px-2 bg-[#152127] text-[#5c7080] font-mono">Quantum Key Exchange</span>
              </div>
            </div>

            {/* Email Login */}
            <div className="space-y-4">
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail size={14} className="text-[#5c7080]" />
                </div>
                <input 
                  type="email" 
                  placeholder="IDENTITY@PRECISO-DATA.COM"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 bg-[#0A1317] border border-[#30404d] rounded-xl text-[#f6f7f9] text-xs font-mono focus:outline-none focus:border-[#2B95D6] transition-all"
                />
              </div>
              <button 
                onClick={handleEmailLogin}
                disabled={loading || !email}
                className="w-full py-3 bg-gradient-to-r from-[#2B95D6] to-[#1e7ab6] hover:brightness-110 text-white rounded-xl font-bold text-[10px] tracking-[0.2em] uppercase shadow-[0_4px_15px_rgba(43,149,214,0.3)] transition-all disabled:opacity-50"
              >
                {loading ? <Spinner size={16} /> : "Request Access Token"}
              </button>
            </div>
          </div>

          {/* Background decoration */}
          <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-[#2B95D6]/10 blur-[50px] rounded-full" />
        </div>

        {/* System Info */}
        <div className="mt-8 flex justify-between items-center px-2">
          <div className="flex flex-col">
            <span className="text-[8px] text-[#5c7080] font-mono uppercase">Node Status</span>
            <span className="text-[9px] text-[#21ce99] font-mono flex items-center gap-1">
              <span className="w-1 h-1 rounded-full bg-[#21ce99]" /> 
              AUTHORIZED
            </span>
          </div>
          <div className="text-right">
            <span className="text-[8px] text-[#5c7080] font-mono uppercase">Handshake Latency</span>
            <div className="text-[9px] text-[#a7b6c2] font-mono">1.22ms</div>
          </div>
        </div>
      </motion.div>
    </BackgroundLines>
  );
}
