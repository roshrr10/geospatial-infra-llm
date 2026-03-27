import { useState } from "react";
import { X, FileDown, Mail, Send, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDownloadReady: () => Promise<void>;
  onEmailSend: (email: string) => Promise<any>;
}

export default function ExportModal({ isOpen, onClose, onDownloadReady, onEmailSend }: ExportModalProps) {
  const [email, setEmail] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  if (!isOpen) return null;

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      await onDownloadReady();
      setSuccessMsg("PDF Downloaded!");
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (e) {
      setErrorMsg("Failed to download PDF.");
      setTimeout(() => setErrorMsg(""), 3000);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !email.includes("@")) return;
    
    setIsSending(true);
    try {
      const result = await onEmailSend(email);
      if (result?.mocked) {
        setSuccessMsg("Email MOCKED (Check .env)");
      } else {
        setSuccessMsg(`Report sent to ${email}`);
      }
      setEmail("");
      setTimeout(() => setSuccessMsg(""), 4000);
    } catch (e) {
      setErrorMsg("Failed to send email.");
      setTimeout(() => setErrorMsg(""), 3000);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="w-full max-w-md bg-white rounded-3xl overflow-hidden shadow-2xl relative z-10"
      >
        <div className="flex items-center justify-between p-6 border-b border-slate-100 bg-slate-50">
          <h3 className="text-sm font-black text-slate-800 uppercase tracking-widest flex items-center gap-2">
            <FileDown size={18} className="text-blue-600" /> Export Options
          </h3>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 bg-white rounded-xl hover:bg-slate-100 transition">
            <X size={16} />
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="space-y-3">
            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Download Local</label>
            <button 
              onClick={handleDownload} disabled={isDownloading}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-2xl text-xs font-bold uppercase transition"
            >
              {isDownloading ? <Loader2 size={16} className="animate-spin" /> : <FileDown size={16} />}
              {isDownloading ? "Generating PDF..." : "Download PDF Report"}
            </button>
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-200" /></div>
            <div className="relative flex justify-center"><span className="bg-white px-4 text-[10px] uppercase font-bold text-slate-300">OR</span></div>
          </div>

          <form onSubmit={handleEmail} className="space-y-3">
            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Send via Email</label>
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <input 
                type="email" placeholder="Enter recipient email..." required
                value={email} onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-11 pr-4 py-3 bg-slate-50 border-2 border-slate-100 rounded-2xl focus:border-blue-500 outline-none text-sm font-medium"
              />
            </div>
            <button 
              type="submit" disabled={isSending || !email}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-slate-900 text-white rounded-2xl text-xs font-bold uppercase transition disabled:opacity-50"
            >
              {isSending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              {isSending ? "Sending Email..." : "Send Report"}
            </button>
          </form>

          <AnimatePresence>
            {successMsg && (
              <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="p-3 bg-emerald-50 text-emerald-700 text-xs font-bold rounded-xl text-center border border-emerald-100">
                {successMsg}
              </motion.div>
            )}
            {errorMsg && (
              <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="p-3 bg-rose-50 text-rose-700 text-xs font-bold rounded-xl text-center border border-rose-100">
                {errorMsg}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
      <div className="fixed inset-0 z-0 bg-transparent" onClick={onClose}></div>
    </div>
  );
}
