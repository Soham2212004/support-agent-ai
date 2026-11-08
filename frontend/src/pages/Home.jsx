import { Link } from "react-router-dom";

const thread = [
  {
    from: "customer",
    text: "Hi, I was charged twice for my March invoice. Can you check?",
  },
  {
    from: "agent",
    text: "I can see two charges of $49 on March 3, and one is a duplicate. I’ve refunded it. It should reach your card in 3 to 5 business days.",
    note: "Source: Billing policy, refunds",
  },
  {
    from: "customer",
    text: "Thanks! Can I also move my team to the annual plan?",
  },
  {
    from: "agent",
    text: "Plan changes need a person. I’ve passed this to Priya on the billing team with our conversation attached. She’ll reply within the hour.",
    note: "Handed to a person",
    handoff: true,
  },
];

const jobs = [
  {
    title: "Answers from your own help docs",
    text: "Replies use your articles, policies and past tickets, and each answer shows which source it came from.",
  },
  {
    title: "Handles the repeat questions",
    text: "Refunds, password resets, shipping status and plan details are answered in seconds, day or night.",
  },
  {
    title: "Hands off the hard ones",
    text: "When a case needs judgment, a person gets the ticket with the full conversation and a short summary.",
  },
  {
    title: "Works where customers already are",
    text: "Email, chat on your website and your help center all feed one shared inbox for your team.",
  },
];

const steps = [
  {
    title: "Connect your knowledge",
    text: "Point Support Agent AI at your help center and past tickets. It reads them and builds its answers from there.",
  },
  {
    title: "Turn it on for one channel",
    text: "Start with website chat or one email address. Your team sees every reply it sends.",
  },
  {
    title: "Review and widen",
    text: "Correct any answer in one click. When you’re happy, switch on more channels.",
  },
];

export default function Home() {
  return (
    <main id="top">
      <section className="hero">
        <div className="hero-copy">
          <h1>Answer every customer before they finish typing.</h1>
          <p className="lede">
            Support Agent AI reads your help docs and past tickets, replies to customers in seconds,
            and hands the hard cases to your team with the full context attached.
          </p>
          <div className="actions">
            <Link className="button" to="/register">
              Try our services
            </Link>
            <a className="button button-ghost" href="#how">
              See how it works
            </a>
          </div>
        </div>

        <div
          className="ticket"
          role="img"
          aria-label="Sample support conversation: the agent refunds a duplicate charge, then hands a plan change to a person."
        >
          <div className="ticket-bar">
            <span>Ticket 4821</span>
            <span className="ticket-status">Resolved in 38 seconds</span>
          </div>
          <ol className="thread">
            {thread.map((m, i) => (
              <li
                key={i}
                className={`msg msg-${m.from}${m.handoff ? " msg-handoff" : ""}`}
                style={{ "--i": i }}
              >
                <p>{m.text}</p>
                {m.note && <span className="msg-note">{m.note}</span>}
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="section" id="what">
        <h2>What it takes off your team’s plate</h2>
        <ul className="jobs">
          {jobs.map((j) => (
            <li key={j.title}>
              <h3>{j.title}</h3>
              <p>{j.text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="section section-tint" id="how">
        <h2>Live in an afternoon</h2>
        <ol className="steps">
          {steps.map((s, i) => (
            <li key={s.title}>
              <span className="step-num">{i + 1}</span>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="section cta" id="contact">
        <h2>See it answer your own tickets.</h2>
        <p>
          Tell us about your company and why you want a support chatbot. We review every request and
          unlock your dashboard once it’s approved.
        </p>
        <Link className="button" to="/register">
          Try our services
        </Link>
      </section>
    </main>
  );
}