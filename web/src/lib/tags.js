import { Brain, Coffee, List } from "lucide-react";

export function tagIcon(tag) {
  if (tag === "Deep work") return Brain;
  if (tag === "Break") return Coffee;
  return List;
}
