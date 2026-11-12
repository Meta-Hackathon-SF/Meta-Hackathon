import { GraduationCap } from "lucide-react";
import { Link } from "react-router";
import PageFrame from "../layouts/PageFrame";
import { photo } from "../data/demo";

export default function CampusPage() {
  return (
    <PageFrame title="Campus" description="A place for your college community.">
      <section className="card campus-placeholder">
        <img src={photo("campus")} alt="A university campus" />
        <div>
          <span className="feature-icon">
            <GraduationCap size={32} />
          </span>
          <h2>Your campus. Closer together.</h2>
          <p>
            A space for college communities, class chats, campus events,
            housing, and people who share your interests.
          </p>
          <p className="muted">
            Campus is coming later. This is a temporary placeholder for our
            hackathon team to build on.
          </p>
          <Link className="button-primary" to="/">
            Back to Feed
          </Link>
        </div>
      </section>
    </PageFrame>
  );
}
