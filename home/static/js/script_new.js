function openVideoModal(videoId) {
  const modal = document.getElementById("videoModal")
  const videoFrame = document.getElementById("videoFrame")

  // Construct YouTube embed URL with the provided video ID
  const videoUrl = `https://www.youtube.com/embed/${videoId}?autoplay=1`

  videoFrame.src = videoUrl
  modal.style.display = "block"
  document.body.style.overflow = "hidden"
}

function closeVideoModal() {
  const modal = document.getElementById("videoModal")
  const videoFrame = document.getElementById("videoFrame")

  videoFrame.src = ""
  modal.style.display = "none"
  document.body.style.overflow = "auto"
}

// Close modal when clicking outside
window.onclick = (event) => {
  const modal = document.getElementById("videoModal")
  if (event.target === modal) {
    closeVideoModal()
  }
}

// Close modal with Escape key
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeVideoModal()
  }
})

// Smooth animations on load
document.addEventListener("DOMContentLoaded", () => {
  const elements = document.querySelectorAll(".hero-section > *, .signup-section > *")
  elements.forEach((element, index) => {
    element.style.opacity = "0"
    element.style.transform = "translateY(20px)"
    element.style.transition = "all 0.6s ease"

    setTimeout(() => {
      element.style.opacity = "1"
      element.style.transform = "translateY(0)"
    }, index * 100)
  })

  // Animate video items
  const videoItems = document.querySelectorAll(".video-item")
  videoItems.forEach((item, index) => {
    item.style.opacity = "0"
    item.style.transform = "translateY(30px)"
    item.style.transition = "all 0.6s ease"

    setTimeout(
      () => {
        item.style.opacity = "1"
        item.style.transform = "translateY(0)"
      },
      300 + index * 150,
    )
  })
})
