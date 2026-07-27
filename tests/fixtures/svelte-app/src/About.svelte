<script>
  let count = 0;
  function onSubmit() {
    if (count < 10) {
      count += 1;
    }
  }
</script>

<div class="about-page">
  <h1>About us</h1>
  <button data-testid="submit-btn" on:click={onSubmit}>Submit</button>
</div>

<style>
  .about-page { color: red; }
</style>
