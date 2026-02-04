export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#1a1c1e] text-[#f6f7f9]">
      {children}
    </div>
  );
}
