export default function Privacy() {
  return (
    <main className="page">
      <p className="eyebrow">LEGAL</p>
      <h1>Privacy Policy</h1>
      <p className="page-lede">Last updated: 2026. This is a template and has not been reviewed by a lawyer.</p>

      <div className="doc-section">
        <h2>What we store</h2>
        <p>
          Your account details, uploaded documents and FAQ entries, bot settings, and the conversations your
          chatbot has with your website's visitors, including a visitor's name and email when they start a chat.
        </p>
      </div>
      <div className="doc-section">
        <h2>Who sees it</h2>
        <p>
          Your data is visible to you in your dashboard, and to our staff only for support purposes, which is
          logged. Visitor messages and document passages are sent to the AI provider configured for your account
          to generate answers.
        </p>
      </div>
      <div className="doc-section">
        <h2>Retention and deletion</h2>
        <p>
          Conversations are kept until you delete them. You can export or permanently delete your entire account
          and all associated data at any time from your dashboard's Account tab. A visitor can also request export
          or deletion of their own chat history directly.
        </p>
      </div>
      <div className="doc-section">
        <h2>Your responsibilities</h2>
        <p>
          If you publish a chatbot on your website, you are responsible for disclosing to your visitors that an AI
          chatbot is collecting their name, email, and messages.
        </p>
      </div>
    </main>
  );
}