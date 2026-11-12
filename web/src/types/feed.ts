export interface Author {
  name: string;
  avatar: string;
  community?: string;
}

export interface PostImage {
  src: string;
  alt: string;
}

export interface Comment {
  id: string;
  text: string;
}

export interface Post {
  id: string;
  author: Author;
  timestamp: string;
  visibility: "Public" | "Friends";
  text: string;
  images?: PostImage[];
  reactionCount: number;
  commentCount: number;
  shareCount: number;
  liked?: boolean;
  saved?: boolean;
  hidden?: boolean;
  comments?: Comment[];
  event?: { day: string; month: string; title: string; location: string };
}
