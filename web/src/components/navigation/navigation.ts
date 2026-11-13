import {
  Bookmark,
  CalendarDays,
  Clapperboard,
  GraduationCap,
  History,
  Home,
  LayoutList,
  MessageCircle,
  Sparkles,
  Store,
  Users,
  UsersRound,
} from "lucide-react";

export const primaryNavigation = [
  { to: "/", label: "Home", icon: Home },
  { to: "/friends", label: "Friends", icon: Users },
  { to: "/watch", label: "Video", icon: Clapperboard },
  { to: "/marketplace", label: "Marketplace", icon: Store },
  { to: "/groups", label: "Groups", icon: UsersRound },
];

export const sidebarNavigation = [
  { to: "/campus", label: "Campus", icon: GraduationCap, color: "blue" },
  { to: "/friends", label: "Friends", icon: Users, color: "blue" },
  { to: "/memories", label: "Memories", icon: History, color: "cyan" },
  { to: "/saved", label: "Saved", icon: Bookmark, color: "purple" },
  { to: "/groups", label: "Groups", icon: UsersRound, color: "blue" },
  {
    to: "/constellations",
    label: "Constellations",
    icon: Sparkles,
    color: "purple",
  },
  { to: "/watch", label: "Video", icon: Clapperboard, color: "pink" },
  { to: "/marketplace", label: "Marketplace", icon: Store, color: "cyan" },
  { to: "/events", label: "Events", icon: CalendarDays, color: "red" },
];

export const extraNavigation = [
  {
    to: "/groups",
    label: "Meta AI Explorers",
    icon: Sparkles,
    color: "purple",
  },
  { to: "/", label: "Feeds", icon: LayoutList, color: "blue" },
  { to: "/messages", label: "Messenger", icon: MessageCircle, color: "blue" },
];
