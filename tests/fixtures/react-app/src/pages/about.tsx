export function About() {
  return (
    <div className="about-page">
      <h1>About us</h1>
      <button data-testid="submit-btn" id="submitBtn" aria-label="Submit form">
        Submit
      </button>
      <input name="email" type="text" aria-label="Email address" />
      <a href="/contact" className="nav-link primary">Contact</a>
    </div>
  );
}
