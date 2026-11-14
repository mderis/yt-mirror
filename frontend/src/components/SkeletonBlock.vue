<script setup lang="ts">
/**
 * A grey block that stands in for something that is still loading
 * (docs/DESIGN.md section 4). Its size comes from the classes of its user.
 * It says nothing to a screen reader: the loading state has its own words.
 */
</script>

<template>
  <span class="block rounded-sm bg-track" aria-hidden="true" data-skeleton />
</template>
