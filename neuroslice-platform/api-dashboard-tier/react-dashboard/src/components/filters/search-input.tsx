import type { InputHTMLAttributes } from "react";
import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";

export function SearchInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="relative">
      <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-mutedText" />
      <Input className="pl-9" {...props} />
    </div>
  );
}
