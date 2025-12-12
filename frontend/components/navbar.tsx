import Link from "next/link";

const NAV_ITEMS: Array<{ href: string; label: string }> = [
  { href: "/", label: "Query" },
  { href: "/schema", label: "Schema" },
  { href: "/history", label: "History" },
  { href: "/stats", label: "Stats" }
];

export function Navbar() {
  return (
    <header className="border-b border-neutral-800 bg-neutral-950/60 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
        <Link href="/" className="text-sm font-semibold text-white">
          LLM DW
        </Link>
        <nav className="flex gap-4 text-sm text-neutral-200">
          {NAV_ITEMS.map((item) => (
            <Link key={item.href} href={item.href} className="hover:text-white">
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}

